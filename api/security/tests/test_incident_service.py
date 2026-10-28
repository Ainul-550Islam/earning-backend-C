"""
Enhanced Incident Service Tests
Comprehensive test suite for incident management functionality
Author: System Security Team
Version: 2.0.0
"""
from datetime import timedelta

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from rest_framework.test import APITestCase

from ..services.IncidentService import IncidentService
from .factories import (
    UserFactory, StaffUserFactory, SecurityIncidentFactory,
    SecurityLogFactory, UserBanFactory, ThreatIntelligenceFactory
)
from api.security.models import SecurityIncident


class IncidentServiceTest(TestCase):
    """Test IncidentService class"""
    
    def setUp(self):
        self.service = IncidentService()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        cache.clear()
    
    def test_incident_service_initialization(self):
        """Test IncidentService initialization"""
        self.assertIsNotNone(self.service.cache_prefix)
        self.assertIsNotNone(self.service.logger)
        self.assertIsNotNone(self.service.default_severity)
        self.assertIsNotNone(self.service.default_status)
    
    def test_incident_service_default_config(self):
        """Test default configuration"""
        self.assertEqual(self.service.default_severity, 'medium')
        self.assertEqual(self.service.default_status, 'open')
        self.assertEqual(self.service.cache_prefix, "incident_service")
    
    def test_create_incident_from_fraud_detection(self):
        """Test creating incident from fraud detection"""
        fraud_data = {
            'user_id': self.user.id,
            'fraud_score': 85,
            'fraud_type': 'account_takeover',
            'ip_address': '192.168.1.100',
            'user_agent': 'TestAgent/1.0',
            'risk_factors': ['suspicious_location', 'unusual_device'],
            'timestamp': timezone.now().isoformat()
        }
        
        with patch('api.security.models.SecurityIncident.objects.create') as mock_create:
            mock_instance = MagicMock()
            mock_instance.id = 'test-id'
            mock_create.return_value = mock_instance
            
            result = self.service.create_incident_from_fraud_detection(fraud_data)
            
            self.assertEqual(result, mock_instance)
            mock_create.assert_called_once()
            
            # Check call arguments
            call_args = mock_create.call_args[1]
            self.assertEqual(call_args['user'], self.user)
            self.assertEqual(call_args['incident_type'], 'fraud_detection')
            self.assertEqual(call_args['severity'], 'high')
            self.assertIn('account_takeover', call_args['title'])
    
    def test_create_incident_from_fraud_detection_high_score(self):
        """Test creating incident from high fraud score"""
        fraud_data = {
            'user_id': self.user.id,
            'fraud_score': 95,  # High score
            'fraud_type': 'account_takeover',
            'ip_address': '192.168.1.100',
            'user_agent': 'TestAgent/1.0'
        }
        
        with patch('api.security.models.SecurityIncident.objects.create') as mock_create:
            mock_instance = MagicMock()
            mock_instance.id = 'test-id'
            mock_create.return_value = mock_instance
            
            result = self.service.create_incident_from_fraud_detection(fraud_data)
            
            call_args = mock_create.call_args[1]
            self.assertEqual(call_args['severity'], 'critical')
    
    def test_create_incident_from_fraud_detection_low_score(self):
        """Test not creating incident from low fraud score"""
        fraud_data = {
            'user_id': self.user.id,
            'fraud_score': 45,  # Below threshold
            'fraud_type': 'suspicious_activity',
            'ip_address': '192.168.1.100',
            'user_agent': 'TestAgent/1.0'
        }
        
        result = self.service.create_incident_from_fraud_detection(fraud_data)
        
        self.assertIsNone(result)
    
    def test_create_incident_from_fraud_detection_missing_data(self):
        """Test creating incident with missing fraud data"""
        fraud_data = {
            'user_id': self.user.id,
            'fraud_score': 85,
            # Missing required fields
        }
        
        with patch('api.security.models.SecurityIncident.objects.create') as mock_create:
            mock_instance = MagicMock()
            mock_instance.id = 'test-id'
            mock_create.return_value = mock_instance
            
            result = self.service.create_incident_from_fraud_detection(fraud_data)
            
            # Should still create incident with default values
            self.assertEqual(result, mock_instance)
            mock_create.assert_called_once()
    
    def test_create_incident_from_security_event(self):
        """Test creating incident from security event"""
        security_event = {
            'user_id': self.user.id,
            'event_type': 'suspicious_login',
            'severity': 'high',
            'ip_address': '192.168.1.100',
            'user_agent': 'TestAgent/1.0',
            'description': 'Multiple failed login attempts',
            'metadata': {'attempts': 5, 'time_window': '1 hour'}
        }
        
        with patch('api.security.models.SecurityIncident.objects.create') as mock_create:
            mock_instance = MagicMock()
            mock_instance.id = 'test-id'
            mock_create.return_value = mock_instance
            
            result = self.service.create_incident_from_security_event(security_event)
            
            self.assertEqual(result, mock_instance)
            mock_create.assert_called_once()
            
            call_args = mock_create.call_args[1]
            self.assertEqual(call_args['user'], self.user)
            self.assertEqual(call_args['incident_type'], 'security_event')
            self.assertEqual(call_args['severity'], 'high')
            self.assertIn('suspicious_login', call_args['title'])
    
    def test_create_incident_from_security_event_auto_escalation(self):
        """Test automatic escalation for critical security events"""
        security_event = {
            'user_id': self.user.id,
            'event_type': 'data_breach',
            'severity': 'critical',
            'ip_address': '192.168.1.100',
            'user_agent': 'TestAgent/1.0',
            'description': 'Potential data breach detected'
        }
        
        with patch('api.security.models.SecurityIncident.objects.create') as mock_create:
            mock_instance = MagicMock()
            mock_instance.id = 'test-id'
            mock_create.return_value = mock_instance
            
            result = self.service.create_incident_from_security_event(security_event)
            
            call_args = mock_create.call_args[1]
            self.assertEqual(call_args['severity'], 'critical')
            self.assertEqual(call_args['status'], 'investigating')  # Auto-escalate
    
    def test_check_existing_incident(self):
        """Test checking for existing incidents"""
        with patch('api.security.models.SecurityIncident.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.exists.return_value = True
            mock_filter.return_value = mock_queryset
            
            result = self.service._check_existing_incident(
                self.user.id,
                'fraud_detection',
                'account_takeover'
            )
            
            self.assertTrue(result)
            mock_filter.assert_called_once()
    
    def test_check_existing_incident_none(self):
        """Test checking for non-existing incidents"""
        with patch('api.security.models.SecurityIncident.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.exists.return_value = False
            mock_filter.return_value = mock_queryset
            
            result = self.service._check_existing_incident(
                self.user.id,
                'fraud_detection',
                'account_takeover'
            )
            
            self.assertFalse(result)
    
    def test_link_incident_to_security_logs(self):
        """Test linking incident to security logs"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_filter.return_value = mock_queryset
            
            result = self.service._link_incident_to_security_logs(incident)
            
            self.assertEqual(result['linked_logs'], 5)
            mock_filter.assert_called_once()
    
    def test_link_incident_to_user_ban(self):
        """Test linking incident to user ban"""
        incident = SecurityIncidentFactory(user=self.user)
        ban = UserBanFactory(user=self.user)
        
        with patch('api.security.models.UserBan.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.first.return_value = ban
            mock_filter.return_value = mock_queryset
            
            result = self.service._link_incident_to_user_ban(incident)
            
            self.assertEqual(result, ban)
            mock_filter.assert_called_once()
    
    def test_link_incident_to_user_ban_none(self):
        """Test linking incident to non-existing user ban"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch('api.security.models.UserBan.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.first.return_value = None
            mock_filter.return_value = mock_queryset
            
            result = self.service._link_incident_to_user_ban(incident)
            
            self.assertIsNone(result)
    
    def test_escalate_incident(self):
        """Test incident escalation"""
        incident = SecurityIncidentFactory(
            user=self.user,
            severity='medium',
            status='open'
        )
        
        with patch.object(incident, 'save') as mock_save:
            result = self.service.escalate_incident(
                incident.id,
                new_severity='high',
                new_status='investigating',
                escalation_reason='Critical pattern detected'
            )
            
            self.assertEqual(result['severity'], 'high')
            self.assertEqual(result['status'], 'investigating')
            self.assertIn('escalation_reason', result['metadata'])
            mock_save.assert_called_once()
    
    def test_escalate_incident_not_found(self):
        """Test escalating non-existing incident"""
        with patch('api.security.models.SecurityIncident.objects.get') as mock_get:
            mock_get.side_effect = SecurityIncident.DoesNotExist()
            
            result = self.service.escalate_incident(
                'non-existent-id',
                new_severity='high'
            )
            
            self.assertIsNone(result)
    
    def test_resolve_incident(self):
        """Test incident resolution"""
        incident = SecurityIncidentFactory(
            user=self.user,
            status='investigating'
        )
        
        with patch.object(incident, 'save') as mock_save:
            result = self.service.resolve_incident(
                incident.id,
                resolution='False positive',
                resolved_by=self.staff_user
            )
            
            self.assertEqual(result['status'], 'resolved')
            self.assertEqual(result['resolved_by'], self.staff_user)
            self.assertIsNotNone(result['resolved_at'])
            mock_save.assert_called_once()
    
    def test_resolve_incident_not_found(self):
        """Test resolving non-existing incident"""
        with patch('api.security.models.SecurityIncident.objects.get') as mock_get:
            mock_get.side_effect = SecurityIncident.DoesNotExist()
            
            result = self.service.resolve_incident(
                'non-existent-id',
                resolution='Test resolution'
            )
            
            self.assertIsNone(result)
    
    def test_assign_incident(self):
        """Test incident assignment"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch.object(incident, 'save') as mock_save:
            result = self.service.assign_incident(
                incident.id,
                assigned_to=self.staff_user
            )
            
            self.assertEqual(result['assigned_to'], self.staff_user)
            mock_save.assert_called_once()
    
    def test_assign_incident_not_found(self):
        """Test assigning non-existing incident"""
        with patch('api.security.models.SecurityIncident.objects.get') as mock_get:
            mock_get.side_effect = SecurityIncident.DoesNotExist()
            
            result = self.service.assign_incident(
                'non-existent-id',
                assigned_to=self.staff_user
            )
            
            self.assertIsNone(result)
    
    def test_update_incident_evidence(self):
        """Test updating incident evidence"""
        incident = SecurityIncidentFactory(user=self.user)
        new_evidence = {
            'ip_addresses': ['192.168.1.100', '192.168.1.101'],
            'user_agents': ['TestAgent/1.0', 'MaliciousAgent/1.0'],
            'timestamps': ['2023-01-01T00:00:00Z', '2023-01-01T01:00:00Z']
        }
        
        with patch.object(incident, 'save') as mock_save:
            result = self.service.update_incident_evidence(
                incident.id,
                new_evidence
            )
            
            self.assertEqual(result['evidence'], new_evidence)
            mock_save.assert_called_once()
    
    def test_update_incident_evidence_merge(self):
        """Test merging incident evidence"""
        incident = SecurityIncidentFactory(
            user=self.user,
            evidence={
                'ip_addresses': ['192.168.1.100'],
                'user_agents': ['TestAgent/1.0']
            }
        )
        
        new_evidence = {
            'ip_addresses': ['192.168.1.101'],
            'timestamps': ['2023-01-01T00:00:00Z']
        }
        
        with patch.object(incident, 'save') as mock_save:
            result = self.service.update_incident_evidence(
                incident.id,
                new_evidence,
                merge=True
            )
            
            # Should merge evidence
            self.assertIn('192.168.1.100', result['evidence']['ip_addresses'])
            self.assertIn('192.168.1.101', result['evidence']['ip_addresses'])
            self.assertIn('TestAgent/1.0', result['evidence']['user_agents'])
            self.assertIn('timestamps', result['evidence'])
    
    def test_get_incident_statistics(self):
        """Test getting incident statistics"""
        with patch('api.security.models.SecurityIncident.objects') as mock_model:
            mock_model.objects.count.return_value = 100
            mock_model.objects.filter.return_value.count.return_value = 25
            
            result = self.service.get_incident_statistics()
            
            self.assertEqual(result['total_incidents'], 100)
            self.assertEqual(result['open_incidents'], 25)
            self.assertIn('timestamp', result)
    
    def test_get_incident_statistics_by_severity(self):
        """Test getting incident statistics by severity"""
        with patch('api.security.models.SecurityIncident.objects') as mock_model:
            mock_model.objects.values.return_value.annotate.return_value = [
                {'severity': 'low', 'count': 10},
                {'severity': 'medium', 'count': 20},
                {'severity': 'high', 'count': 15},
                {'severity': 'critical', 'count': 5}
            ]
            
            result = self.service.get_incident_statistics(by_severity=True)
            
            self.assertIn('severity_breakdown', result)
            self.assertEqual(result['severity_breakdown']['low'], 10)
            self.assertEqual(result['severity_breakdown']['critical'], 5)
    
    def test_get_incident_statistics_by_type(self):
        """Test getting incident statistics by type"""
        with patch('api.security.models.SecurityIncident.objects') as mock_model:
            mock_model.objects.values.return_value.annotate.return_value = [
                {'incident_type': 'fraud_detection', 'count': 30},
                {'incident_type': 'security_event', 'count': 25},
                {'incident_type': 'data_breach', 'count': 5}
            ]
            
            result = self.service.get_incident_statistics(by_type=True)
            
            self.assertIn('type_breakdown', result)
            self.assertEqual(result['type_breakdown']['fraud_detection'], 30)
            self.assertEqual(result['type_breakdown']['data_breach'], 5)
    
    def test_search_incidents(self):
        """Test searching incidents"""
        search_criteria = {
            'user_id': self.user.id,
            'severity': 'high',
            'status': 'open',
            'date_from': timezone.now() - timezone.timedelta(days=7),
            'date_to': timezone.now()
        }
        
        with patch('api.security.models.SecurityIncident.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.__iter__.return_value = [
                SecurityIncidentFactory(user=self.user),
                SecurityIncidentFactory(user=self.user)
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.search_incidents(search_criteria)
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['incidents']), 2)
            mock_filter.assert_called_once()
    
    def test_search_incidents_empty_criteria(self):
        """Test searching incidents with empty criteria"""
        result = self.service.search_incidents({})
        
        self.assertIn('incidents', result)
        self.assertIn('count', result)
    
    def test_export_incidents(self):
        """Test exporting incidents"""
        with patch('api.security.models.SecurityIncident.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value = [
                {
                    'incident_id': 'INC-001',
                    'user_id': self.user.id,
                    'severity': 'high',
                    'status': 'open',
                    'created_at': timezone.now()
                },
                {
                    'incident_id': 'INC-002',
                    'user_id': self.user.id,
                    'severity': 'medium',
                    'status': 'resolved',
                    'created_at': timezone.now()
                }
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.export_incidents(
                format='json',
                criteria={'user_id': self.user.id}
            )
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['incident_id'], 'INC-001')
            self.assertEqual(result[1]['severity'], 'medium')
    
    def test_export_incidents_csv(self):
        """Test exporting incidents in CSV format"""
        with patch('api.security.models.SecurityIncident.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value = [
                {
                    'incident_id': 'INC-001',
                    'user_id': self.user.id,
                    'severity': 'high',
                    'status': 'open',
                    'created_at': timezone.now()
                }
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.export_incidents(
                format='csv',
                criteria={'user_id': self.user.id}
            )
            
            self.assertIn('incident_id', result)
            self.assertIn('INC-001', result)
    
    def test_get_incident_timeline(self):
        """Test getting incident timeline"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch.object(self.service, '_build_incident_timeline') as mock_timeline:
            mock_timeline.return_value = [
                {
                    'timestamp': timezone.now(),
                    'event_type': 'incident_created',
                    'description': 'Incident created',
                    'details': {}
                }
            ]
            
            result = self.service.get_incident_timeline(incident.id)
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['event_type'], 'incident_created')
            mock_timeline.assert_called_once_with(incident)
    
    def test_build_incident_timeline(self):
        """Test building incident timeline"""
        incident = SecurityIncidentFactory(user=self.user)
        
        # Create related security logs
        security_logs = SecurityLogFactory.create_batch(
            3,
            user=self.user,
            created_at=timezone.now() - timezone.timedelta(hours=1)
        )
        
        timeline = self.service._build_incident_timeline(incident)
        
        self.assertIsInstance(timeline, list)
        # Should include incident creation and related events
        self.assertGreater(len(timeline), 0)
    
    def test_auto_escalate_incidents(self):
        """Test automatic incident escalation"""
        # Create incidents that should be escalated
        incidents = [
            SecurityIncidentFactory(
                user=self.user,
                severity='high',
                status='open',
                created_at=timezone.now() - timezone.timedelta(hours=25)  # Old
            ),
            SecurityIncidentFactory(
                user=self.user,
                severity='critical',
                status='open',
                created_at=timezone.now() - timezone.timedelta(hours=1)  # Recent but critical
            )
        ]
        
        with patch.object(self.service, 'escalate_incident') as mock_escalate:
            mock_escalate.return_value = MagicMock()
            
            result = self.service.auto_escalate_incidents()
            
            self.assertEqual(result['escalated_count'], 2)
            self.assertEqual(mock_escalate.call_count, 2)
    
    def test_auto_escalate_incidents_criteria(self):
        """Test automatic incident escalation with custom criteria"""
        escalation_criteria = {
            'age_hours': 12,  # Escalate incidents older than 12 hours
            'min_severity': 'medium',  # Only medium and above
            'current_status': 'open'
        }
        
        # Create incident that meets criteria
        incident = SecurityIncidentFactory(
            user=self.user,
            severity='medium',
            status='open',
            created_at=timezone.now() - timezone.timedelta(hours=13)
        )
        
        with patch.object(self.service, 'escalate_incident') as mock_escalate:
            mock_escalate.return_value = MagicMock()
            
            result = self.service.auto_escalate_incidents(escalation_criteria)
            
            self.assertEqual(result['escalated_count'], 1)
            mock_escalate.assert_called_once()
    
    def test_close_old_incidents(self):
        """Test closing old incidents"""
        # Create old incidents
        old_incidents = SecurityIncidentFactory.create_batch(
            3,
            user=self.user,
            status='open',
            created_at=timezone.now() - timezone.timedelta(days=31)
        )
        
        with patch.object(self.service, 'resolve_incident') as mock_resolve:
            mock_resolve.return_value = MagicMock()
            
            result = self.service.close_old_incidents(days=30)
            
            self.assertEqual(result['closed_count'], 3)
            self.assertEqual(mock_resolve.call_count, 3)
    
    def test_get_incident_metrics(self):
        """Test getting incident metrics"""
        with patch('api.security.models.SecurityIncident.objects') as mock_model:
            mock_model.objects.count.return_value = 100
            mock_model.objects.filter.return_value.count.return_value = 25
            mock_model.objects.filter.return_value.aggregate.return_value = {
                'avg_resolution_time': 48.5,
                'median_resolution_time': 36.0
            }
            
            result = self.service.get_incident_metrics()
            
            self.assertEqual(result['total_incidents'], 100)
            self.assertEqual(result['open_incidents'], 25)
            self.assertEqual(result['avg_resolution_time'], 48.5)
            self.assertEqual(result['median_resolution_time'], 36.0)
    
    def test_get_user_incident_history(self):
        """Test getting user incident history"""
        with patch('api.security.models.SecurityIncident.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [
                SecurityIncidentFactory(user=self.user),
                SecurityIncidentFactory(user=self.user)
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_user_incident_history(self.user.id)
            
            self.assertEqual(result['total_incidents'], 5)
            self.assertEqual(len(result['incidents']), 2)
            mock_filter.assert_called_once_with(user_id=self.user.id)
    
    def test_create_incident_from_multiple_events(self):
        """Test creating incident from multiple security events"""
        security_events = [
            {
                'event_type': 'failed_login',
                'severity': 'medium',
                'ip_address': '192.168.1.100',
                'timestamp': timezone.now() - timedelta(hours=2)
            },
            {
                'event_type': 'suspicious_location',
                'severity': 'high',
                'ip_address': '192.168.1.100',
                'timestamp': timezone.now() - timedelta(hours=1)
            },
            {
                'event_type': 'account_lockout',
                'severity': 'high',
                'ip_address': '192.168.1.100',
                'timestamp': timezone.now()
            }
        ]
        
        with patch('api.security.models.SecurityIncident.objects.create') as mock_create:
            mock_instance = MagicMock()
            mock_instance.id = 'test-id'
            mock_create.return_value = mock_instance
            
            result = self.service.create_incident_from_multiple_events(
                self.user.id,
                security_events
            )
            
            self.assertEqual(result, mock_instance)
            mock_create.assert_called_once()
            
            call_args = mock_create.call_args[1]
            self.assertEqual(call_args['user'], self.user)
            self.assertEqual(call_args['incident_type'], 'security_event')
            self.assertEqual(call_args['severity'], 'high')  # Highest severity
            self.assertIn('multiple security events', call_args['title'])
    
    def test_create_incident_from_multiple_events_empty(self):
        """Test creating incident from empty events list"""
        result = self.service.create_incident_from_multiple_events(
            self.user.id,
            []
        )
        
        self.assertIsNone(result)
    
    def test_validate_incident_data(self):
        """Test incident data validation"""
        valid_data = {
            'user_id': self.user.id,
            'incident_type': 'fraud_detection',
            'severity': 'high',
            'title': 'Test Incident',
            'description': 'Test description'
        }
        
        result = self.service._validate_incident_data(valid_data)
        
        self.assertTrue(result['valid'])
        self.assertNotIn('errors', result)
    
    def test_validate_incident_data_invalid(self):
        """Test incident data validation with invalid data"""
        invalid_data = {
            'user_id': 'invalid_id',
            'incident_type': '',
            'severity': 'invalid_severity',
            'title': '',
            'description': ''
        }
        
        result = self.service._validate_incident_data(invalid_data)
        
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
        self.assertGreater(len(result['errors']), 0)
    
    def test_get_incident_summary(self):
        """Test getting incident summary"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch.object(self.service, '_get_incident_summary_data') as mock_summary:
            mock_summary.return_value = {
                'incident_id': incident.incident_id,
                'user_id': self.user.id,
                'severity': incident.severity,
                'status': incident.status,
                'related_events': 5,
                'timeline_events': 3
            }
            
            result = self.service.get_incident_summary(incident.id)
            
            self.assertEqual(result['incident_id'], incident.incident_id)
            self.assertEqual(result['related_events'], 5)
            self.assertEqual(result['timeline_events'], 3)
            mock_summary.assert_called_once_with(incident)
    
    def test_get_incident_summary_data(self):
        """Test getting incident summary data"""
        incident = SecurityIncidentFactory(user=self.user)
        
        # Create related security logs
        security_logs = SecurityLogFactory.create_batch(
            3,
            user=self.user,
            created_at=timezone.now() - timedelta(hours=1)
        )
        
        summary = self.service._get_incident_summary_data(incident)
        
        self.assertEqual(summary['incident_id'], incident.incident_id)
        self.assertEqual(summary['user_id'], self.user.id)
        self.assertEqual(summary['severity'], incident.severity)
        self.assertEqual(summary['status'], incident.status)
        self.assertIn('related_events', summary)
        self.assertIn('timeline_events', summary)
    
    def test_bulk_create_incidents(self):
        """Test bulk creating incidents"""
        incident_data = [
            {
                'user_id': self.user.id,
                'incident_type': 'fraud_detection',
                'severity': 'high',
                'title': 'Incident 1',
                'description': 'Description 1'
            },
            {
                'user_id': self.user.id,
                'incident_type': 'security_event',
                'severity': 'medium',
                'title': 'Incident 2',
                'description': 'Description 2'
            }
        ]
        
        with patch('api.security.models.SecurityIncident.objects.bulk_create') as mock_bulk_create:
            mock_instances = [MagicMock(), MagicMock()]
            mock_bulk_create.return_value = mock_instances
            
            result = self.service.bulk_create_incidents(incident_data)
            
            self.assertEqual(len(result), 2)
            mock_bulk_create.assert_called_once()
    
    def test_bulk_update_incidents(self):
        """Test bulk updating incidents"""
        incident_ids = ['id1', 'id2']
        update_data = {
            'status': 'resolved',
            'resolved_by': self.staff_user
        }
        
        with patch('api.security.models.SecurityIncident.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.update.return_value = 2
            mock_filter.return_value = mock_queryset
            
            result = self.service.bulk_update_incidents(incident_ids, update_data)
            
            self.assertEqual(result['updated_count'], 2)
            mock_filter.assert_called_once()
    
    def test_get_incident_trends(self):
        """Test getting incident trends"""
        with patch('api.security.models.SecurityIncident.objects') as mock_model:
            mock_model.objects.extra.return_value = [
                {'date': '2023-01-01', 'count': 10},
                {'date': '2023-01-02', 'count': 15},
                {'date': '2023-01-03', 'count': 12}
            ]
            
            result = self.service.get_incident_trends(days=7)
            
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0]['date'], '2023-01-01')
            self.assertEqual(result[0]['count'], 10)
    
    def test_get_incident_heatmap_data(self):
        """Test getting incident heatmap data"""
        with patch('api.security.models.SecurityIncident.objects') as mock_model:
            mock_model.objects.extra.return_value = [
                {'hour': 9, 'count': 5},
                {'hour': 14, 'count': 12},
                {'hour': 18, 'count': 8}
            ]
            
            result = self.service.get_incident_heatmap_data()
            
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0]['hour'], 9)
            self.assertEqual(result[0]['count'], 5)
    
    def test_get_incident_correlation_analysis(self):
        """Test incident correlation analysis"""
        with patch.object(self.service, '_analyze_incident_correlations') as mock_analyze:
            mock_analyze.return_value = {
                'correlated_incidents': 3,
                'common_factors': ['ip_address', 'user_agent'],
                'correlation_score': 0.85
            }
            
            result = self.service.get_incident_correlation_analysis(
                incident_id='test-id'
            )
            
            self.assertEqual(result['correlated_incidents'], 3)
            self.assertIn('ip_address', result['common_factors'])
            self.assertEqual(result['correlation_score'], 0.85)
    
    def test_analyze_incident_correlations(self):
        """Test analyzing incident correlations"""
        incident = SecurityIncidentFactory(user=self.user)
        
        # Create related incidents
        related_incidents = SecurityIncidentFactory.create_batch(
            2,
            user=self.user,
            evidence={
                'ip_addresses': ['192.168.1.100'],
                'user_agents': ['TestAgent/1.0']
            }
        )
        
        correlation = self.service._analyze_incident_correlations(incident)
        
        self.assertIsInstance(correlation, dict)
        self.assertIn('correlated_incidents', correlation)
        self.assertIn('common_factors', correlation)
        self.assertIn('correlation_score', correlation)
    
    def test_generate_incident_report(self):
        """Test generating incident report"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch.object(self.service, '_generate_incident_report_data') as mock_report:
            mock_report.return_value = {
                'incident_id': incident.incident_id,
                'summary': 'Test summary',
                'timeline': [],
                'recommendations': [],
                'metrics': {}
            }
            
            result = self.service.generate_incident_report(incident.id)
            
            self.assertEqual(result['incident_id'], incident.incident_id)
            self.assertIn('summary', result)
            self.assertIn('timeline', result)
            self.assertIn('recommendations', result)
            self.assertIn('metrics', result)
    
    def test_generate_incident_report_data(self):
        """Test generating incident report data"""
        incident = SecurityIncidentFactory(user=self.user)
        
        # Create related data
        security_logs = SecurityLogFactory.create_batch(
            2,
            user=self.user
        )
        
        report_data = self.service._generate_incident_report_data(incident)
        
        self.assertEqual(report_data['incident_id'], incident.incident_id)
        self.assertIn('summary', report_data)
        self.assertIn('timeline', report_data)
        self.assertIn('recommendations', report_data)
        self.assertIn('metrics', report_data)
    
    def test_archive_old_incidents(self):
        """Test archiving old incidents"""
        # Create old incidents
        old_incidents = SecurityIncidentFactory.create_batch(
            3,
            user=self.user,
            status='resolved',
            created_at=timezone.now() - timedelta(days=365)
        )
        
        with patch.object(self.service, '_archive_incident') as mock_archive:
            mock_archive.return_value = True
            
            result = self.service.archive_old_incidents(days=180)
            
            self.assertEqual(result['archived_count'], 3)
            self.assertEqual(mock_archive.call_count, 3)
    
    def test_archive_incident(self):
        """Test archiving individual incident"""
        incident = SecurityIncidentFactory(
            user=self.user,
            status='resolved'
        )
        
        with patch('api.security.models.SecurityIncidentArchive.objects.create') as mock_create:
            mock_archive = MagicMock()
            mock_create.return_value = mock_archive
            
            with patch.object(incident, 'delete') as mock_delete:
                result = self.service._archive_incident(incident)
                
                self.assertTrue(result)
                mock_create.assert_called_once()
                mock_delete.assert_called_once()
    
    def test_get_archived_incidents(self):
        """Test getting archived incidents"""
        with patch('api.security.models.SecurityIncidentArchive.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 10
            mock_queryset.__iter__.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_archived_incidents(
                date_from=timezone.now() - timedelta(days=30)
            )
            
            self.assertEqual(result['count'], 10)
            self.assertEqual(len(result['incidents']), 2)
    
    def test_restore_archived_incident(self):
        """Test restoring archived incident"""
        with patch('api.security.models.SecurityIncidentArchive.objects.get') as mock_get:
            mock_archive = MagicMock()
            mock_archive.incident_data = {
                'user_id': self.user.id,
                'incident_type': 'fraud_detection',
                'severity': 'high',
                'title': 'Restored Incident'
            }
            mock_get.return_value = mock_archive
            
            with patch('api.security.models.SecurityIncident.objects.create') as mock_create:
                mock_incident = MagicMock()
                mock_incident.id = 'restored-id'
                mock_create.return_value = mock_incident
                
                result = self.service.restore_archived_incident('archive-id')
                
                self.assertEqual(result, mock_incident)
                mock_create.assert_called_once()
    
    def test_delete_archived_incident(self):
        """Test deleting archived incident"""
        with patch('api.security.models.SecurityIncidentArchive.objects.get') as mock_get:
            mock_archive = MagicMock()
            mock_get.return_value = mock_archive
            
            with patch.object(mock_archive, 'delete') as mock_delete:
                result = self.service.delete_archived_incident('archive-id')
                
                self.assertTrue(result)
                mock_delete.assert_called_once()
    
    def test_get_incident_performance_metrics(self):
        """Test getting incident performance metrics"""
        with patch.object(self.service, '_calculate_performance_metrics') as mock_calculate:
            mock_calculate.return_value = {
                'avg_resolution_time': 24.5,
                'avg_escalation_time': 2.5,
                'resolution_rate': 0.85,
                'escalation_rate': 0.15
            }
            
            result = self.service.get_incident_performance_metrics(
                days=30
            )
            
            self.assertEqual(result['avg_resolution_time'], 24.5)
            self.assertEqual(result['avg_escalation_time'], 2.5)
            self.assertEqual(result['resolution_rate'], 0.85)
            self.assertEqual(result['escalation_rate'], 0.15)
    
    def test_calculate_performance_metrics(self):
        """Test calculating performance metrics"""
        # Create test incidents
        incidents = [
            SecurityIncidentFactory(
                user=self.user,
                status='resolved',
                created_at=timezone.now() - timedelta(days=5),
                resolved_at=timezone.now() - timedelta(days=4)
            ),
            SecurityIncidentFactory(
                user=self.user,
                status='open',
                created_at=timezone.now() - timedelta(days=2)
            )
        ]
        
        metrics = self.service._calculate_performance_metrics(incidents)
        
        self.assertIn('avg_resolution_time', metrics)
        self.assertIn('resolution_rate', metrics)
        self.assertIn('escalation_rate', metrics)
    
    def test_get_incident_recommendations(self):
        """Test getting incident recommendations"""
        incident = SecurityIncidentFactory(
            user=self.user,
            incident_type='fraud_detection',
            severity='high'
        )
        
        recommendations = self.service.get_incident_recommendations(incident.id)
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        
        # Should have relevant recommendations
        for rec in recommendations:
            self.assertIn('type', rec)
            self.assertIn('description', rec)
            self.assertIn('priority', rec)
    
    def test_generate_incident_recommendations(self):
        """Test generating incident recommendations"""
        incident = SecurityIncidentFactory(
            user=self.user,
            incident_type='fraud_detection',
            severity='high'
        )
        
        recommendations = self.service._generate_incident_recommendations(incident)
        
        self.assertIsInstance(recommendations, list)
        
        # Should have recommendations based on incident type and severity
        fraud_recommendations = [r for r in recommendations if 'fraud' in r['type'].lower()]
        self.assertGreater(len(fraud_recommendations), 0)
    
    def test_get_incident_alert_rules(self):
        """Test getting incident alert rules"""
        with patch('api.security.models.IncidentAlertRule.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.__iter__.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_incident_alert_rules()
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['rules']), 2)
    
    def test_create_incident_alert_rule(self):
        """Test creating incident alert rule"""
        rule_data = {
            'name': 'High Severity Alert',
            'conditions': {
                'severity': 'high',
                'incident_type': 'fraud_detection'
            },
            'actions': ['send_email', 'create_task'],
            'is_active': True
        }
        
        with patch('api.security.models.IncidentAlertRule.objects.create') as mock_create:
            mock_rule = MagicMock()
            mock_rule.id = 'rule-id'
            mock_create.return_value = mock_rule
            
            result = self.service.create_incident_alert_rule(rule_data)
            
            self.assertEqual(result, mock_rule)
            mock_create.assert_called_once()
    
    def test_update_incident_alert_rule(self):
        """Test updating incident alert rule"""
        rule_data = {
            'name': 'Updated Alert Rule',
            'is_active': False
        }
        
        with patch('api.security.models.IncidentAlertRule.objects.get') as mock_get:
            mock_rule = MagicMock()
            mock_get.return_value = mock_rule
            
            with patch.object(mock_rule, 'save') as mock_save:
                result = self.service.update_incident_alert_rule('rule-id', rule_data)
                
                self.assertEqual(result, mock_rule)
                mock_save.assert_called_once()
    
    def test_delete_incident_alert_rule(self):
        """Test deleting incident alert rule"""
        with patch('api.security.models.IncidentAlertRule.objects.get') as mock_get:
            mock_rule = MagicMock()
            mock_get.return_value = mock_rule
            
            with patch.object(mock_rule, 'delete') as mock_delete:
                result = self.service.delete_incident_alert_rule('rule-id')
                
                self.assertTrue(result)
                mock_delete.assert_called_once()
    
    def test_check_incident_alert_rules(self):
        """Test checking incident alert rules"""
        incident = SecurityIncidentFactory(
            user=self.user,
            severity='high',
            incident_type='fraud_detection'
        )
        
        with patch.object(self.service, '_evaluate_alert_rules') as mock_evaluate:
            mock_evaluate.return_value = [
                {
                    'rule_id': 'rule-1',
                    'rule_name': 'High Severity Alert',
                    'matched_conditions': ['severity'],
                    'actions': ['send_email']
                }
            ]
            
            result = self.service.check_incident_alert_rules(incident)
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['rule_id'], 'rule-1')
            self.assertIn('send_email', result[0]['actions'])
    
    def test_evaluate_alert_rules(self):
        """Test evaluating alert rules"""
        incident = SecurityIncidentFactory(
            user=self.user,
            severity='high',
            incident_type='fraud_detection'
        )
        
        with patch('api.security.models.IncidentAlertRule.objects.filter') as mock_filter:
            mock_rule = MagicMock()
            mock_rule.conditions = {
                'severity': 'high',
                'incident_type': 'fraud_detection'
            }
            mock_rule.actions = ['send_email']
            mock_rule.is_active = True
            mock_filter.return_value = [mock_rule]
            
            result = self.service._evaluate_alert_rules(incident)
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['rule_id'], mock_rule.id)
    
    def test_execute_alert_actions(self):
        """Test executing alert actions"""
        alert_data = {
            'rule_id': 'rule-1',
            'rule_name': 'Test Alert',
            'incident_id': 'incident-1',
            'actions': ['send_email', 'create_task']
        }
        
        with patch.object(self.service, '_send_alert_email') as mock_email:
            with patch.object(self.service, '_create_alert_task') as mock_task:
                mock_email.return_value = True
                mock_task.return_value = True
                
                result = self.service._execute_alert_actions(alert_data)
                
                self.assertTrue(result['send_email'])
                self.assertTrue(result['create_task'])
                mock_email.assert_called_once()
                mock_task.assert_called_once()
    
    def test_send_alert_email(self):
        """Test sending alert email"""
        alert_data = {
            'rule_name': 'Test Alert',
            'incident_id': 'incident-1',
            'incident_severity': 'high'
        }
        
        with patch('django.core.mail.send_mail') as mock_send:
            mock_send.return_value = True
            
            result = self.service._send_alert_email(alert_data)
            
            self.assertTrue(result)
            mock_send.assert_called_once()
    
    def test_create_alert_task(self):
        """Test creating alert task"""
        alert_data = {
            'rule_name': 'Test Alert',
            'incident_id': 'incident-1',
            'incident_severity': 'high'
        }
        
        with patch('api.security.models.AlertTask.objects.create') as mock_create:
            mock_task = MagicMock()
            mock_task.id = 'task-id'
            mock_create.return_value = mock_task
            
            result = self.service._create_alert_task(alert_data)
            
            self.assertEqual(result, mock_task)
            mock_create.assert_called_once()
    
    def test_get_incident_workflows(self):
        """Test getting incident workflows"""
        with patch('api.security.models.IncidentWorkflow.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 3
            mock_queryset.__iter__.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_incident_workflows()
            
            self.assertEqual(result['count'], 3)
            self.assertEqual(len(result['workflows']), 2)
    
    def test_create_incident_workflow(self):
        """Test creating incident workflow"""
        workflow_data = {
            'name': 'Standard Incident Response',
            'steps': [
                {'name': 'Initial Assessment', 'order': 1},
                {'name': 'Investigation', 'order': 2},
                {'name': 'Resolution', 'order': 3}
            ],
            'is_active': True
        }
        
        with patch('api.security.models.IncidentWorkflow.objects.create') as mock_create:
            mock_workflow = MagicMock()
            mock_workflow.id = 'workflow-id'
            mock_create.return_value = mock_workflow
            
            result = self.service.create_incident_workflow(workflow_data)
            
            self.assertEqual(result, mock_workflow)
            mock_create.assert_called_once()
    
    def test_apply_incident_workflow(self):
        """Test applying incident workflow"""
        incident = SecurityIncidentFactory(user=self.user)
        workflow_id = 'workflow-1'
        
        with patch('api.security.models.IncidentWorkflow.objects.get') as mock_get:
            mock_workflow = MagicMock()
            mock_workflow.steps = [
                {'name': 'Initial Assessment', 'order': 1},
                {'name': 'Investigation', 'order': 2}
            ]
            mock_get.return_value = mock_workflow
            
            with patch.object(self.service, '_create_workflow_steps') as mock_create:
                mock_create.return_value = [MagicMock(), MagicMock()]
                
                result = self.service.apply_incident_workflow(incident.id, workflow_id)
                
                self.assertEqual(len(result), 2)
                mock_create.assert_called_once()
    
    def test_create_workflow_steps(self):
        """Test creating workflow steps"""
        incident = SecurityIncidentFactory(user=self.user)
        steps = [
            {'name': 'Initial Assessment', 'order': 1},
            {'name': 'Investigation', 'order': 2}
        ]
        
        with patch('api.security.models.IncidentWorkflowStep.objects.bulk_create') as mock_bulk_create:
            mock_steps = [MagicMock(), MagicMock()]
            mock_bulk_create.return_value = mock_steps
            
            result = self.service._create_workflow_steps(incident, steps)
            
            self.assertEqual(len(result), 2)
            mock_bulk_create.assert_called_once()
    
    def test_get_workflow_step_status(self):
        """Test getting workflow step status"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch('api.security.models.IncidentWorkflowStep.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 2
            mock_queryset.filter.return_value.count.return_value = 1
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_workflow_step_status(incident.id)
            
            self.assertEqual(result['total_steps'], 2)
            self.assertEqual(result['completed_steps'], 1)
            self.assertEqual(result['progress_percentage'], 50.0)
    
    def test_update_workflow_step(self):
        """Test updating workflow step"""
        step_id = 'step-1'
        update_data = {
            'status': 'completed',
            'completed_by': self.staff_user,
            'notes': 'Step completed successfully'
        }
        
        with patch('api.security.models.IncidentWorkflowStep.objects.get') as mock_get:
            mock_step = MagicMock()
            mock_get.return_value = mock_step
            
            with patch.object(mock_step, 'save') as mock_save:
                result = self.service.update_workflow_step(step_id, update_data)
                
                self.assertEqual(result, mock_step)
                mock_save.assert_called_once()
    
    def test_get_incident_checklist(self):
        """Test getting incident checklist"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch.object(self.service, '_generate_incident_checklist') as mock_checklist:
            mock_checklist.return_value = [
                {
                    'category': 'Initial Response',
                    'items': [
                        {'name': 'Verify incident details', 'completed': False},
                        {'name': 'Assess impact', 'completed': False}
                    ]
                }
            ]
            
            result = self.service.get_incident_checklist(incident.id)
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['category'], 'Initial Response')
            self.assertEqual(len(result[0]['items']), 2)
    
    def test_generate_incident_checklist(self):
        """Test generating incident checklist"""
        incident = SecurityIncidentFactory(
            user=self.user,
            incident_type='fraud_detection',
            severity='high'
        )
        
        checklist = self.service._generate_incident_checklist(incident)
        
        self.assertIsInstance(checklist, list)
        self.assertGreater(len(checklist), 0)
        
        # Should have categories based on incident type
        categories = [item['category'] for item in checklist]
        self.assertIn('Initial Response', categories)
        self.assertIn('Investigation', categories)
    
    def test_update_checklist_item(self):
        """Test updating checklist item"""
        incident = SecurityIncidentFactory(user=self.user)
        item_data = {
            'category': 'Initial Response',
            'item_name': 'Verify incident details',
            'completed': True,
            'completed_by': self.staff_user,
            'notes': 'Details verified'
        }
        
        with patch.object(self.service, '_save_checklist_item') as mock_save:
            mock_save.return_value = True
            
            result = self.service.update_checklist_item(incident.id, item_data)
            
            self.assertTrue(result)
            mock_save.assert_called_once()
    
    def test_save_checklist_item(self):
        """Test saving checklist item"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch('api.security.models.IncidentChecklistItem.objects.update_or_create') as mock_update:
            mock_item = MagicMock()
            mock_update.return_value = (mock_item, True)
            
            result = self.service._save_checklist_item(
                incident,
                'Initial Response',
                'Verify incident details',
                True,
                self.staff_user,
                'Details verified'
            )
            
            self.assertEqual(result, mock_item)
            mock_update.assert_called_once()
    
    def test_get_incident_communications(self):
        """Test getting incident communications"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch('api.security.models.IncidentCommunication.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 3
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_incident_communications(incident.id)
            
            self.assertEqual(result['count'], 3)
            self.assertEqual(len(result['communications']), 2)
    
    def test_create_incident_communication(self):
        """Test creating incident communication"""
        incident = SecurityIncidentFactory(user=self.user)
        comm_data = {
            'type': 'email',
            'recipient': 'security@company.com',
            'subject': 'Security Incident Update',
            'message': 'Incident update...',
            'sent_by': self.staff_user
        }
        
        with patch('api.security.models.IncidentCommunication.objects.create') as mock_create:
            mock_comm = MagicMock()
            mock_comm.id = 'comm-id'
            mock_create.return_value = mock_comm
            
            result = self.service.create_incident_communication(incident.id, comm_data)
            
            self.assertEqual(result, mock_comm)
            mock_create.assert_called_once()
    
    def test_get_incident_documents(self):
        """Test getting incident documents"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch('api.security.models.IncidentDocument.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 2
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_incident_documents(incident.id)
            
            self.assertEqual(result['count'], 2)
            self.assertEqual(len(result['documents']), 2)
    
    def test_upload_incident_document(self):
        """Test uploading incident document"""
        incident = SecurityIncidentFactory(user=self.user)
        
        with patch('api.security.models.IncidentDocument.objects.create') as mock_create:
            mock_document = MagicMock()
            mock_document.id = 'doc-id'
            mock_create.return_value = mock_document
            
            result = self.service.upload_incident_document(
                incident.id,
                'test_document.pdf',
                'application/pdf',
                1024,
                self.staff_user
            )
            
            self.assertEqual(result, mock_document)
            mock_create.assert_called_once()
    
    def test_get_incident_knowledge_base(self):
        """Test getting incident knowledge base"""
        with patch('api.security.models.IncidentKnowledgeBase.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_incident_knowledge_base(
                incident_type='fraud_detection'
            )
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['articles']), 2)
    
    def test_create_knowledge_base_article(self):
        """Test creating knowledge base article"""
        article_data = {
            'title': 'Handling Fraud Detection Incidents',
            'content': 'Detailed guide...',
            'incident_types': ['fraud_detection'],
            'tags': ['fraud', 'detection'],
            'created_by': self.staff_user
        }
        
        with patch('api.security.models.IncidentKnowledgeBase.objects.create') as mock_create:
            mock_article = MagicMock()
            mock_article.id = 'article-id'
            mock_create.return_value = mock_article
            
            result = self.service.create_knowledge_base_article(article_data)
            
            self.assertEqual(result, mock_article)
            mock_create.assert_called_once()
    
    def test_get_incident_templates(self):
        """Test getting incident templates"""
        with patch('api.security.models.IncidentTemplate.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 3
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_incident_templates()
            
            self.assertEqual(result['count'], 3)
            self.assertEqual(len(result['templates']), 2)
    
    def test_create_incident_template(self):
        """Test creating incident template"""
        template_data = {
            'name': 'Standard Fraud Response',
            'incident_type': 'fraud_detection',
            'severity': 'high',
            'description_template': 'Fraud detected: {details}',
            'steps': [
                'Verify user identity',
                'Check transaction history',
                'Contact user'
            ],
            'created_by': self.staff_user
        }
        
        with patch('api.security.models.IncidentTemplate.objects.create') as mock_create:
            mock_template = MagicMock()
            mock_template.id = 'template-id'
            mock_create.return_value = mock_template
            
            result = self.service.create_incident_template(template_data)
            
            self.assertEqual(result, mock_template)
            mock_create.assert_called_once()
    
    def test_apply_incident_template(self):
        """Test applying incident template"""
        template_id = 'template-1'
        template_data = {
            'user_id': self.user.id,
            'custom_data': {'additional_info': 'Test'}
        }
        
        with patch('api.security.models.IncidentTemplate.objects.get') as mock_get:
            mock_template = MagicMock()
            mock_template.incident_type = 'fraud_detection'
            mock_template.severity = 'high'
            mock_template.description_template = 'Fraud detected: {details}'
            mock_template.steps = ['Step 1', 'Step 2']
            mock_get.return_value = mock_template
            
            with patch('api.security.models.SecurityIncident.objects.create') as mock_create:
                mock_incident = MagicMock()
                mock_incident.id = 'incident-id'
                mock_create.return_value = mock_incident
                
                result = self.service.apply_incident_template(template_id, template_data)
                
                self.assertEqual(result, mock_incident)
                mock_create.assert_called_once()
    
    def test_get_incident_metrics_dashboard(self):
        """Test getting incident metrics dashboard"""
        with patch.object(self.service, 'get_incident_statistics') as mock_stats:
            with patch.object(self.service, 'get_incident_trends') as mock_trends:
                with patch.object(self.service, 'get_incident_heatmap_data') as mock_heatmap:
                    
                    mock_stats.return_value = {
                        'total_incidents': 100,
                        'open_incidents': 25
                    }
                    mock_trends.return_value = [
                        {'date': '2023-01-01', 'count': 10}
                    ]
                    mock_heatmap.return_value = [
                        {'hour': 9, 'count': 5}
                    ]
                    
                    result = self.service.get_incident_metrics_dashboard()
                    
                    self.assertIn('statistics', result)
                    self.assertIn('trends', result)
                    self.assertIn('heatmap', result)
                    self.assertEqual(result['statistics']['total_incidents'], 100)
    
    def test_get_incident_performance_dashboard(self):
        """Test getting incident performance dashboard"""
        with patch.object(self.service, 'get_incident_performance_metrics') as mock_metrics:
            with patch.object(self.service, 'get_incident_correlation_analysis') as mock_correlation:
                
                mock_metrics.return_value = {
                    'avg_resolution_time': 24.5,
                    'resolution_rate': 0.85
                }
                mock_correlation.return_value = {
                    'correlated_incidents': 3,
                    'correlation_score': 0.85
                }
                
                result = self.service.get_incident_performance_dashboard()
                
                self.assertIn('performance_metrics', result)
                self.assertIn('correlation_analysis', result)
                self.assertEqual(result['performance_metrics']['avg_resolution_time'], 24.5)
    
    def test_get_incident_alert_dashboard(self):
        """Test getting incident alert dashboard"""
        with patch.object(self.service, 'get_incident_alert_rules') as mock_rules:
            with patch.object(self.service, 'get_recent_alerts') as mock_alerts:
                
                mock_rules.return_value = {
                    'count': 5,
                    'rules': [MagicMock(), MagicMock()]
                }
                mock_alerts.return_value = {
                    'count': 10,
                    'alerts': [MagicMock(), MagicMock()]
                }
                
                result = self.service.get_incident_alert_dashboard()
                
                self.assertIn('alert_rules', result)
                self.assertIn('recent_alerts', result)
                self.assertEqual(result['alert_rules']['count'], 5)
    
    def test_get_recent_alerts(self):
        """Test getting recent alerts"""
        with patch('api.security.models.IncidentAlert.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 10
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_recent_alerts(hours=24)
            
            self.assertEqual(result['count'], 10)
            self.assertEqual(len(result['alerts']), 2)
    
    def test_get_incident_team_performance(self):
        """Test getting incident team performance"""
        with patch.object(self.service, '_calculate_team_performance') as mock_calculate:
            mock_calculate.return_value = {
                'team_members': [
                    {
                        'user_id': self.staff_user.id,
                        'username': self.staff_user.username,
                        'incidents_handled': 15,
                        'avg_resolution_time': 18.5,
                        'resolution_rate': 0.93
                    }
                ],
                'team_avg_resolution_time': 20.2,
                'team_resolution_rate': 0.89
            }
            
            result = self.service.get_incident_team_performance(days=30)
            
            self.assertIn('team_members', result)
            self.assertIn('team_avg_resolution_time', result)
            self.assertEqual(len(result['team_members']), 1)
    
    def test_calculate_team_performance(self):
        """Test calculating team performance"""
        # Create test incidents assigned to staff user
        incidents = [
            SecurityIncidentFactory(
                user=self.user,
                assigned_to=self.staff_user,
                status='resolved',
                created_at=timezone.now() - timedelta(days=5),
                resolved_at=timezone.now() - timedelta(days=4)
            ),
            SecurityIncidentFactory(
                user=self.user,
                assigned_to=self.staff_user,
                status='open',
                created_at=timezone.now() - timedelta(days=2)
            )
        ]
        
        performance = self.service._calculate_team_performance(incidents)
        
        self.assertIn('team_members', performance)
        self.assertIn('team_avg_resolution_time', performance)
        self.assertIn('team_resolution_rate', performance)
    
    def test_get_incident_cost_analysis(self):
        """Test getting incident cost analysis"""
        with patch.object(self.service, '_calculate_incident_costs') as mock_calculate:
            mock_calculate.return_value = {
                'total_cost': 15000.00,
                'cost_per_incident': 750.00,
                'cost_breakdown': {
                    'personnel': 10000.00,
                    'resources': 3000.00,
                    'downtime': 2000.00
                },
                'cost_trends': [
                    {'month': '2023-01', 'cost': 12000.00},
                    {'month': '2023-02', 'cost': 15000.00}
                ]
            }
            
            result = self.service.get_incident_cost_analysis(days=90)
            
            self.assertEqual(result['total_cost'], 15000.00)
            self.assertEqual(result['cost_per_incident'], 750.00)
            self.assertIn('cost_breakdown', result)
            self.assertIn('cost_trends', result)
    
    def test_calculate_incident_costs(self):
        """Test calculating incident costs"""
        # Create test incidents
        incidents = [
            SecurityIncidentFactory(
                user=self.user,
                severity='high',
                status='resolved',
                created_at=timezone.now() - timedelta(days=5),
                resolved_at=timezone.now() - timedelta(days=4)
            ),
            SecurityIncidentFactory(
                user=self.user,
                severity='medium',
                status='resolved',
                created_at=timezone.now() - timedelta(days=3),
                resolved_at=timezone.now() - timedelta(days=2)
            )
        ]
        
        costs = self.service._calculate_incident_costs(incidents)
        
        self.assertIn('total_cost', costs)
        self.assertIn('cost_per_incident', costs)
        self.assertIn('cost_breakdown', costs)
        self.assertIn('cost_trends', costs)
    
    def test_get_incident_sla_compliance(self):
        """Test getting incident SLA compliance"""
        with patch.object(self.service, '_calculate_sla_compliance') as mock_calculate:
            mock_calculate.return_value = {
                'overall_compliance': 0.85,
                'sla_breakdown': {
                    'response_time': 0.90,
                    'resolution_time': 0.80,
                    'communication': 0.85
                },
                'violations': 3,
                'total_incidents': 20
            }
            
            result = self.service.get_incident_sla_compliance(days=30)
            
            self.assertEqual(result['overall_compliance'], 0.85)
            self.assertIn('sla_breakdown', result)
            self.assertEqual(result['violations'], 3)
    
    def test_calculate_sla_compliance(self):
        """Test calculating SLA compliance"""
        # Create test incidents with different SLA compliance
        incidents = [
            SecurityIncidentFactory(
                user=self.user,
                severity='high',
                status='resolved',
                created_at=timezone.now() - timedelta(days=5),
                resolved_at=timezone.now() - timedelta(days=4)
            ),
            SecurityIncidentFactory(
                user=self.user,
                severity='medium',
                status='open',
                created_at=timezone.now() - timedelta(days=2)
            )
        ]
        
        compliance = self.service._calculate_sla_compliance(incidents)
        
        self.assertIn('overall_compliance', compliance)
        self.assertIn('sla_breakdown', compliance)
        self.assertIn('violations', compliance)
        self.assertIn('total_incidents', compliance)
    
    def test_get_incident_root_cause_analysis(self):
        """Test getting incident root cause analysis"""
        with patch.object(self.service, '_analyze_root_causes') as mock_analyze:
            mock_analyze.return_value = {
                'primary_causes': [
                    {
                        'cause': 'Insufficient authentication',
                        'frequency': 15,
                        'impact': 'high'
                    },
                    {
                        'cause': 'Lack of monitoring',
                        'frequency': 8,
                        'impact': 'medium'
                    }
                ],
                'recommendations': [
                    'Implement multi-factor authentication',
                    'Enhance monitoring systems'
                ],
                'prevention_measures': [
                    'Regular security audits',
                    'Employee training'
                ]
            }
            
            result = self.service.get_incident_root_cause_analysis(days=90)
            
            self.assertEqual(len(result['primary_causes']), 2)
            self.assertEqual(len(result['recommendations']), 2)
            self.assertEqual(len(result['prevention_measures']), 2)
    
    def test_analyze_root_causes(self):
        """Test analyzing root causes"""
        # Create test incidents
        incidents = [
            SecurityIncidentFactory(
                user=self.user,
                incident_type='fraud_detection',
                severity='high',
                evidence={'root_cause': 'Insufficient authentication'}
            ),
            SecurityIncidentFactory(
                user=self.user,
                incident_type='security_event',
                severity='medium',
                evidence={'root_cause': 'Lack of monitoring'}
            )
        ]
        
        analysis = self.service._analyze_root_causes(incidents)
        
        self.assertIn('primary_causes', analysis)
        self.assertIn('recommendations', analysis)
        self.assertIn('prevention_measures', analysis)
    
    def test_get_incident_learning_insights(self):
        """Test getting incident learning insights"""
        with patch.object(self.service, '_generate_learning_insights') as mock_insights:
            mock_insights.return_value = {
                'key_learnings': [
                    'Early detection reduces impact by 60%',
                    'Multi-factor authentication prevents 80% of fraud attempts'
                ],
                'improvement_areas': [
                    'Response time optimization',
                    'Communication protocols'
                ],
                'success_stories': [
                    'Quick resolution of critical incident',
                    'Effective team coordination'
                ]
            }
            
            result = self.service.get_incident_learning_insights(days=180)
            
            self.assertEqual(len(result['key_learnings']), 2)
            self.assertEqual(len(result['improvement_areas']), 2)
            self.assertEqual(len(result['success_stories']), 2)
    
    def test_generate_learning_insights(self):
        """Test generating learning insights"""
        # Create test incidents
        incidents = [
            SecurityIncidentFactory(
                user=self.user,
                incident_type='fraud_detection',
                severity='high',
                status='resolved',
                created_at=timezone.now() - timedelta(days=30),
                resolved_at=timezone.now() - timedelta(days=29)
            ),
            SecurityIncidentFactory(
                user=self.user,
                incident_type='security_event',
                severity='medium',
                status='resolved',
                created_at=timezone.now() - timedelta(days=20),
                resolved_at=timezone.now() - timedelta(days=19)
            )
        ]
        
        insights = self.service._generate_learning_insights(incidents)
        
        self.assertIn('key_learnings', insights)
        self.assertIn('improvement_areas', insights)
        self.assertIn('success_stories', insights)
    
    def test_get_incident_forecasting(self):
        """Test getting incident forecasting"""
        with patch.object(self.service, '_forecast_incident_trends') as mock_forecast:
            mock_forecast.return_value = {
                'forecast_period': '30 days',
                'predicted_incidents': 25,
                'confidence_interval': [20, 30],
                'trend_direction': 'increasing',
                'risk_factors': [
                    'Seasonal patterns',
                    'System updates'
                ]
            }
            
            result = self.service.get_incident_forecasting(days=30)
            
            self.assertEqual(result['predicted_incidents'], 25)
            self.assertEqual(result['trend_direction'], 'increasing')
            self.assertIn('confidence_interval', result)
    
    def test_forecast_incident_trends(self):
        """Test forecasting incident trends"""
        # Create historical data
        historical_incidents = [
            {'date': '2023-01-01', 'count': 10},
            {'date': '2023-01-02', 'count': 15},
            {'date': '2023-01-03', 'count': 12},
            {'date': '2023-01-04', 'count': 18},
            {'date': '2023-01-05', 'count': 20}
        ]
        
        forecast = self.service._forecast_incident_trends(historical_incidents)
        
        self.assertIn('forecast_period', forecast)
        self.assertIn('predicted_incidents', forecast)
        self.assertIn('confidence_interval', forecast)
        self.assertIn('trend_direction', forecast)
    
    def test_get_incident_benchmarking(self):
        """Test getting incident benchmarking"""
        with patch.object(self.service, '_benchmark_incident_metrics') as mock_benchmark:
            mock_benchmark.return_value = {
                'industry_average': {
                    'avg_resolution_time': 48.0,
                    'resolution_rate': 0.82,
                    'escalation_rate': 0.18
                },
                'your_metrics': {
                    'avg_resolution_time': 36.0,
                    'resolution_rate': 0.89,
                    'escalation_rate': 0.12
                },
                'comparison': {
                    'resolution_time': 'better',
                    'resolution_rate': 'better',
                    'escalation_rate': 'better'
                },
                'percentile_rank': 85
            }
            
            result = self.service.get_incident_benchmarking(days=90)
            
            self.assertEqual(result['percentile_rank'], 85)
            self.assertEqual(result['comparison']['resolution_time'], 'better')
    
    def test_benchmark_incident_metrics(self):
        """Test benchmarking incident metrics"""
        # Create test incidents
        incidents = [
            SecurityIncidentFactory(
                user=self.user,
                severity='high',
                status='resolved',
                created_at=timezone.now() - timedelta(days=5),
                resolved_at=timezone.now() - timedelta(days=4)
            )
        ]
        
        benchmark = self.service._benchmark_incident_metrics(incidents)
        
        self.assertIn('industry_average', benchmark)
        self.assertIn('your_metrics', benchmark)
        self.assertIn('comparison', benchmark)
        self.assertIn('percentile_rank', benchmark)
    
    def test_get_incident_optimization_suggestions(self):
        """Test getting incident optimization suggestions"""
        with patch.object(self.service, '_generate_optimization_suggestions') as mock_suggestions:
            mock_suggestions.return_value = {
                'process_improvements': [
                    {
                        'area': 'Response Time',
                        'current': '36 hours',
                        'target': '24 hours',
                        'suggestion': 'Implement automated triage',
                        'potential_savings': '25% reduction'
                    }
                ],
                'resource_optimization': [
                    {
                        'resource': 'Personnel',
                        'current_utilization': '85%',
                        'optimal_utilization': '75%',
                        'suggestion': 'Cross-train team members'
                    }
                ],
                'technology_improvements': [
                    {
                        'area': 'Monitoring',
                        'suggestion': 'Implement AI-powered detection',
                        'impact': '40% faster detection'
                    }
                ]
            }
            
            result = self.service.get_incident_optimization_suggestions()
            
            self.assertEqual(len(result['process_improvements']), 1)
            self.assertEqual(len(result['resource_optimization']), 1)
            self.assertEqual(len(result['technology_improvements']), 1)
    
    def test_generate_optimization_suggestions(self):
        """Test generating optimization suggestions"""
        # Create test incidents
        incidents = [
            SecurityIncidentFactory(
                user=self.user,
                severity='high',
                status='resolved',
                created_at=timezone.now() - timedelta(days=5),
                resolved_at=timezone.now() - timedelta(days=4)
            )
        ]
        
        suggestions = self.service._generate_optimization_suggestions(incidents)
        
        self.assertIn('process_improvements', suggestions)
        self.assertIn('resource_optimization', suggestions)
        self.assertIn('technology_improvements', suggestions)
    
    def test_get_incident_continuous_improvement(self):
        """Test getting incident continuous improvement"""
        with patch.object(self.service, '_analyze_continuous_improvement') as mock_analyze:
            mock_analyze.return_value = {
                'improvement_cycles': [
                    {
                        'cycle': 'Q1 2023',
                        'initiatives': ['Automated triage', 'Enhanced monitoring'],
                        'results': {
                            'resolution_time_reduction': '20%',
                            'incident_reduction': '15%'
                        }
                    }
                ],
                'current_initiatives': [
                    {
                        'name': 'AI-powered detection',
                        'status': 'in_progress',
                        'expected_completion': '2023-06-01'
                    }
                ],
                'next_cycle_planning': [
                    'Expand automation capabilities',
                    'Implement predictive analytics'
                ]
            }
            
            result = self.service.get_incident_continuous_improvement(days=180)
            
            self.assertEqual(len(result['improvement_cycles']), 1)
            self.assertEqual(len(result['current_initiatives']), 1)
            self.assertEqual(len(result['next_cycle_planning']), 2)
    
    def test_analyze_continuous_improvement(self):
        """Test analyzing continuous improvement"""
        # Create test incidents
        incidents = [
            SecurityIncidentFactory(
                user=self.user,
                severity='high',
                status='resolved',
                created_at=timezone.now() - timedelta(days=90),
                resolved_at=timezone.now() - timedelta(days=89)
            )
        ]
        
        analysis = self.service._analyze_continuous_improvement(incidents)
        
        self.assertIn('improvement_cycles', analysis)
        self.assertIn('current_initiatives', analysis)
        self.assertIn('next_cycle_planning', analysis)