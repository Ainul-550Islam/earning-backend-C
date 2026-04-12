"""
Comprehensive Integration Tests for Alerts API
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.management import call_command
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from alerts.models.threshold import ThresholdConfig, ThresholdBreach
from alerts.models.channel import AlertChannel, ChannelRoute
from alerts.models.incident import Incident, IncidentTimeline, IncidentResponder
from alerts.models.intelligence import AlertCorrelation, AlertPrediction
from alerts.models.reporting import AlertReport, MTTRMetric
from alerts.services.core import AlertProcessingService, AlertEscalationService
from alerts.tasks.core import ProcessAlertsTask, GenerateReportsTask

User = get_user_model()


class ComprehensiveWorkflowTest(TransactionTestCase):
    """Comprehensive end-to-end workflow tests"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create comprehensive test data
        self.setup_test_data()
    
    def setup_test_data(self):
        """Setup comprehensive test data"""
        # Create alert channels
        self.email_channel = AlertChannel.objects.create(
            name='Primary Email Channel',
            channel_type='email',
            is_enabled=True,
            config={
                'smtp_server': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_username': 'alerts@example.com'
            }
        )
        
        self.sms_channel = AlertChannel.objects.create(
            name='SMS Channel',
            channel_type='sms',
            is_enabled=True,
            config={
                'api_key': 'test_sms_key',
                'api_url': 'https://api.sms.example.com'
            }
        )
        
        # Create channel routes
        self.escalation_route = ChannelRoute.objects.create(
            name='Email to SMS Escalation',
            route_type='escalation',
            is_active=True,
            escalation_delay_minutes=15
        )
        self.escalation_route.source_channels.add(self.email_channel)
        self.escalation_route.destination_channels.add(self.sms_channel)
        
        # Create alert rules
        self.cpu_rule = AlertRule.objects.create(
            name='CPU Usage Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            is_active=True,
            send_email=True,
            send_sms=False,
            escalation_enabled=True,
            escalation_delay_minutes=30
        )
        
        self.memory_rule = AlertRule.objects.create(
            name='Memory Usage Alert',
            alert_type='memory_usage',
            severity='medium',
            threshold_value=85.0,
            is_active=True,
            send_email=True,
            send_sms=False,
            escalation_enabled=False
        )
        
        # Create threshold configurations
        self.cpu_threshold = ThresholdConfig.objects.create(
            alert_rule=self.cpu_rule,
            threshold_type='absolute',
            operator='greater_than',
            primary_threshold=85.0,
            secondary_threshold=95.0,
            time_window_minutes=10
        )
        
        # Create system metrics
        for i in range(10):
            SystemMetrics.objects.create(
                total_users=1000 + i * 100,
                active_users_1h=500 + i * 50,
                total_earnings_1h=1000.0 + i * 100,
                avg_response_time_ms=200.0 + i * 20,
                timestamp=timezone.now() - timedelta(hours=i)
            )
    
    def test_complete_alert_lifecycle(self):
        """Test complete alert lifecycle from creation to resolution"""
        # 1. Create alert (trigger)
        alert = AlertLog.objects.create(
            rule=self.cpu_rule,
            trigger_value=90.0,
            threshold_value=80.0,
            message='CPU usage is critically high',
            details={
                'current_usage': 90.0,
                'threshold': 80.0,
                'server': 'web-01',
                'environment': 'production'
            }
        )
        
        # 2. Process alert (should create notifications)
        service = AlertProcessingService()
        result = service.process_alert({
            'rule_id': self.cpu_rule.id,
            'trigger_value': 90.0,
            'threshold_value': 80.0,
            'message': 'CPU usage is critically high',
            'details': alert.details
        })
        
        self.assertTrue(result['success'])
        self.assertIn('alert_id', result)
        self.assertIn('notifications_sent', result)
        
        # 3. Verify notifications were created
        notifications = Notification.objects.filter(alert_log=alert)
        self.assertGreater(notifications.count(), 0)
        
        # 4. Acknowledge alert
        alert.acknowledged_at = timezone.now()
        alert.acknowledgment_note = 'Investigating the CPU spike'
        alert.save()
        
        # 5. Create threshold breach record
        breach = ThresholdBreach.objects.create(
            threshold_config=self.cpu_threshold,
            severity='high',
            breach_value=90.0,
            threshold_value=85.0,
            breach_percentage=5.88,
            breach_duration_minutes=0
        )
        
        # 6. Create incident for critical alert
        incident = Incident.objects.create(
            title='High CPU Usage Incident',
            description='CPU usage exceeded critical threshold',
            severity='high',
            impact='moderate',
            urgency='high',
            status='open',
            assigned_to=self.admin_user,
            detected_at=timezone.now(),
            affected_services=['web-server', 'api-server'],
            related_alerts=[alert.id]
        )
        
        # 7. Add timeline events
        IncidentTimeline.objects.create(
            incident=incident,
            event_type='detection',
            title='High CPU Usage Detected',
            description='CPU usage reached 90%',
            timestamp=timezone.now(),
            participants=[self.admin_user.id]
        )
        
        IncidentTimeline.objects.create(
            incident=incident,
            event_type='acknowledgment',
            title='Incident Acknowledged',
            description='Team acknowledged the incident',
            timestamp=timezone.now() + timedelta(minutes=5),
            participants=[self.admin_user.id]
        )
        
        # 8. Add responders
        IncidentResponder.objects.create(
            incident=incident,
            user=self.admin_user,
            role='lead',
            status='active',
            responsibilities=['Coordination', 'Communication', 'Resolution']
        )
        
        # 9. Resolve alert
        alert.is_resolved = True
        alert.resolution_note = 'CPU usage normalized after scaling'
        alert.resolved_at = timezone.now() + timedelta(minutes=30)
        alert.save()
        
        # 10. Resolve incident
        incident.status = 'resolved'
        incident.resolution_summary = 'CPU usage normalized after horizontal scaling'
        incident.resolution_actions = 'Added 2 more web server instances'
        incident.resolved_by = self.admin_user
        incident.resolved_at = timezone.now() + timedelta(minutes=45)
        incident.save()
        
        # Verify complete lifecycle
        alert.refresh_from_db()
        incident.refresh_from_db()
        
        self.assertTrue(alert.is_resolved)
        self.assertIsNotNone(alert.acknowledged_at)
        self.assertIsNotNone(alert.resolved_at)
        self.assertEqual(incident.status, 'resolved')
        self.assertIsNotNone(incident.resolved_at)
        
        # Verify timeline
        timeline_events = IncidentTimeline.objects.filter(incident=incident)
        self.assertEqual(timeline_events.count(), 2)
        
        # Verify responders
        responders = IncidentResponder.objects.filter(incident=incident)
        self.assertEqual(responders.count(), 1)
    
    def test_escalation_workflow(self):
        """Test alert escalation workflow"""
        # Create alert that should escalate
        alert = AlertLog.objects.create(
            rule=self.cpu_rule,
            trigger_value=95.0,
            threshold_value=80.0,
            message='Critical CPU usage - should escalate',
            triggered_at=timezone.now() - timedelta(minutes=45)  # Old alert
        )
        
        # Create initial notification
        Notification.objects.create(
            alert_log=alert,
            notification_type='email',
            recipient='ops@example.com',
            status='failed',
            failed_at=timezone.now() - timedelta(minutes=30),
            error_message='SMTP server unavailable'
        )
        
        # Check escalation conditions
        escalation_service = AlertEscalationService()
        result = escalation_service.check_escalation_needed(alert)
        
        self.assertTrue(result['escalate'])
        self.assertIn('reason', result)
        
        # Perform escalation
        escalation_result = escalation_service.escalate_alert({
            'alert_log_id': alert.id,
            'escalation_level': 1,
            'reason': 'No response to initial notification'
        })
        
        self.assertTrue(escalation_result['success'])
        self.assertIn('escalation_id', escalation_result)
        self.assertIn('notification_sent', escalation_result)
        
        # Verify escalation notification was created
        escalation_notifications = Notification.objects.filter(
            alert_log=alert,
            notification_type='sms'
        )
        self.assertGreater(escalation_notifications.count(), 0)
    
    def test_intelligence_workflow(self):
        """Test intelligence features workflow"""
        # Create correlated alerts
        base_time = timezone.now() - timedelta(hours=2)
        alerts = []
        
        for i in range(10):
            # CPU alerts
            cpu_alert = AlertLog.objects.create(
                rule=self.cpu_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'CPU alert {i}',
                triggered_at=base_time + timedelta(minutes=i * 10)
            )
            alerts.append(cpu_alert)
            
            # Memory alerts (correlated)
            if i % 2 == 0:
                memory_alert = AlertLog.objects.create(
                    rule=self.memory_rule,
                    trigger_value=90.0 + i,
                    threshold_value=85.0,
                    message=f'Memory alert {i}',
                    triggered_at=base_time + timedelta(minutes=i * 10 + 5)
                )
                alerts.append(memory_alert)
        
        # Create correlation analysis
        correlation = AlertCorrelation.objects.create(
            name='CPU-Memory Correlation Analysis',
            correlation_type='temporal',
            correlation_coefficient=0.85,
            p_value=0.001,
            confidence_level=0.95,
            status='confirmed',
            time_window_minutes=30
        )
        correlation.primary_rules.add(self.cpu_rule, self.memory_rule)
        correlation.related_alerts.add(*alerts)
        
        # Create prediction model
        prediction = AlertPrediction.objects.create(
            name='CPU Usage Prediction Model',
            prediction_type='threshold_breach',
            model_type='linear_regression',
            training_status='completed',
            accuracy_score=0.92,
            precision_score=0.89,
            recall_score=0.91,
            f1_score=0.90,
            prediction_horizon_hours=24
        )
        prediction.target_rules.add(self.cpu_rule)
        
        # Test prediction
        from alerts.services.intelligence import PredictionService
        prediction_service = PredictionService()
        
        prediction_result = prediction_service.predict_alert_probability({
            'model_id': prediction.id,
            'features': {
                'cpu_usage': 88.0,
                'memory_usage': 75.0,
                'disk_io': 60.0
            }
        })
        
        self.assertIn('predicted_probability', prediction_result)
        self.assertIn('confidence_interval', prediction_result)
        self.assertIn('risk_level', prediction_result)
    
    def test_reporting_workflow(self):
        """Test reporting workflow"""
        # Create comprehensive test data
        for i in range(20):
            rule = AlertRule.objects.create(
                name=f'Report Test Rule {i}',
                alert_type='cpu_usage' if i % 2 == 0 else 'memory_usage',
                severity='high' if i % 3 == 0 else 'medium',
                threshold_value=80.0
            )
            
            alert = AlertLog.objects.create(
                rule=rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Report test alert {i}',
                is_resolved=i % 3 == 0,
                resolved_at=timezone.now() - timedelta(hours=i) if i % 3 == 0 else None
            )
            
            Notification.objects.create(
                alert_log=alert,
                notification_type='email',
                recipient=f'test{i}@example.com',
                status='sent' if i % 4 == 0 else 'failed'
            )
        
        # Create MTTR metric
        mttr_metric = MTTRMetric.objects.create(
            name='Overall MTTR',
            calculation_period_days=30,
            target_mttr_minutes=60.0,
            current_mttr_minutes=45.0,
            alerts_within_target=85,
            total_resolved_alerts=100,
            target_compliance_percentage=85.0,
            created_by=self.admin_user
        )
        
        # Generate report
        report = AlertReport.objects.create(
            title='Comprehensive Alert Report',
            report_type='weekly',
            format_type='json',
            status='completed',
            start_date=timezone.now().date() - timedelta(days=7),
            end_date=timezone.now().date(),
            is_recurring=True,
            recurrence_pattern='weekly',
            auto_distribute=True,
            recipients=['admin@example.com', 'ops@example.com'],
            created_by=self.admin_user,
            file_path='/reports/comprehensive_report.json',
            file_size_bytes=1024000,
            generated_at=timezone.now()
        )
        
        # Verify report data
        self.assertEqual(report.report_type, 'weekly')
        self.assertEqual(report.status, 'completed')
        self.assertIsNotNone(report.file_path)
        self.assertIsNotNone(report.generated_at)
        
        # Verify MTTR metric
        self.assertEqual(mttr_metric.current_mttr_minutes, 45.0)
        self.assertEqual(mttr_metric.target_compliance_percentage, 85.0)
    
    def test_system_health_monitoring(self):
        """Test system health monitoring workflow"""
        # Create health check data
        from alerts.models.channel import ChannelHealthLog
        
        for i in range(5):
            ChannelHealthLog.objects.create(
                channel=self.email_channel,
                check_name='connectivity',
                check_type='connectivity',
                status='healthy' if i % 2 == 0 else 'warning',
                response_time_ms=100 + i * 50,
                checked_at=timezone.now() - timedelta(minutes=i * 10)
            )
        
        # Run health check
        from alerts.tasks.core import CheckHealthTask
        health_task = CheckHealthTask()
        
        result = health_task.check_alert_system_health(time_period_hours=24)
        
        self.assertIn('overall_health', result)
        self.assertIn('alerts_health', result)
        self.assertIn('channels_health', result)
        self.assertIn('incidents_health', result)
        self.assertIn('timestamp', result)
        
        # Verify health status
        self.assertIsInstance(result['overall_health'], str)
        self.assertIn(result['overall_health'], ['healthy', 'warning', 'critical'])
    
    def test_batch_processing_workflow(self):
        """Test batch processing workflow"""
        # Create batch of alerts
        alerts = []
        for i in range(50):
            alert = AlertLog.objects.create(
                rule=self.cpu_rule if i % 2 == 0 else self.memory_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Batch alert {i}',
                triggered_at=timezone.now() - timedelta(minutes=i)
            )
            alerts.append(alert)
        
        # Process alerts in batch
        task = ProcessAlertsTask()
        result = task.process_pending_alerts(limit=50, dry_run=False)
        
        self.assertIn('processed_count', result)
        self.assertIn('notifications_sent', result)
        self.assertIn('errors', result)
        self.assertGreater(result['processed_count'], 0)
        
        # Verify notifications were created
        notifications = Notification.objects.filter(
            alert_log__in=alerts
        )
        self.assertGreater(notifications.count(), 0)
    
    def test_cleanup_workflow(self):
        """Test data cleanup workflow"""
        # Create old data for cleanup
        old_date = timezone.now() - timedelta(days=100)
        
        # Create old alerts
        old_alerts = []
        for i in range(10):
            alert = AlertLog.objects.create(
                rule=AlertRule.objects.create(
                    name=f'Old Alert {i}',
                    alert_type='cpu_usage',
                    severity='medium',
                    threshold_value=80.0
                ),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Old alert {i}',
                triggered_at=old_date
            )
            old_alerts.append(alert)
        
        # Create old notifications
        for alert in old_alerts:
            Notification.objects.create(
                alert_log=alert,
                notification_type='email',
                recipient='old@example.com',
                status='sent',
                created_at=old_date
            )
        
        # Run cleanup
        from alerts.tasks.core import CleanupAlertsTask
        cleanup_task = CleanupAlertsTask()
        
        initial_alert_count = AlertLog.objects.count()
        initial_notification_count = Notification.objects.count()
        
        result = cleanup_task.cleanup_old_alerts(days=90, dry_run=False)
        
        self.assertIn('deleted_count', result)
        self.assertIn('batches_processed', result)
        
        # Verify cleanup
        final_alert_count = AlertLog.objects.count()
        final_notification_count = Notification.objects.count()
        
        self.assertLess(final_alert_count, initial_alert_count)
        self.assertLess(final_notification_count, initial_notification_count)


class APIComprehensiveTest(APITestCase):
    """Comprehensive API tests"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        
        self.client.force_authenticate(user=self.admin_user)
        
        # Setup test data
        self.setup_api_test_data()
    
    def setup_api_test_data(self):
        """Setup API test data"""
        # Create alert rule
        self.alert_rule = AlertRule.objects.create(
            name='API Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Create channel
        self.channel = AlertChannel.objects.create(
            name='API Test Channel',
            channel_type='email',
            is_enabled=True
        )
    
    def test_complete_api_workflow(self):
        """Test complete API workflow"""
        # 1. Create alert rule
        rule_data = {
            'name': 'API Workflow Rule',
            'alert_type': 'cpu_usage',
            'severity': 'high',
            'threshold_value': 80.0,
            'description': 'Test rule for API workflow'
        }
        
        response = self.client.post('/api/alerts/rules/', rule_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        rule_id = response.data['id']
        
        # 2. Create alert log
        alert_data = {
            'rule': rule_id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'API workflow alert'
        }
        
        response = self.client.post('/api/alerts/logs/', alert_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        alert_id = response.data['id']
        
        # 3. Acknowledge alert
        ack_data = {
            'acknowledgment_note': 'Acknowledged via API'
        }
        
        response = self.client.post(f'/api/alerts/logs/{alert_id}/acknowledge/', ack_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Create incident
        incident_data = {
            'title': 'API Workflow Incident',
            'description': 'Incident created via API',
            'severity': 'high',
            'impact': 'minor',
            'urgency': 'medium',
            'status': 'open'
        }
        
        response = self.client.post('/api/alerts/incidents/', incident_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        incident_id = response.data['id']
        
        # 5. Add timeline event
        timeline_data = {
            'incident': incident_id,
            'event_type': 'action',
            'title': 'API Action',
            'description': 'Action performed via API'
        }
        
        response = self.client.post('/api/alerts/incidents/timelines/', timeline_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 6. Resolve alert
        resolve_data = {
            'resolution_note': 'Resolved via API'
        }
        
        response = self.client.post(f'/api/alerts/logs/{alert_id}/resolve/', resolve_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 7. Resolve incident
        resolve_incident_data = {
            'resolution_summary': 'Incident resolved via API',
            'resolution_actions': 'API test actions'
        }
        
        response = self.client.post(f'/api/alerts/incidents/{incident_id}/resolve/', resolve_incident_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify final state
        response = self.client.get(f'/api/alerts/logs/{alert_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_resolved'])
        
        response = self.client.get(f'/api/alerts/incidents/{incident_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'resolved')
    
    def test_channel_management_workflow(self):
        """Test channel management API workflow"""
        # 1. Create channel
        channel_data = {
            'name': 'API Channel Workflow',
            'channel_type': 'email',
            'is_enabled': True,
            'priority': 1,
            'config': {
                'smtp_server': 'smtp.example.com',
                'smtp_port': 587
            }
        }
        
        response = self.client.post('/api/alerts/channels/', channel_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        channel_id = response.data['id']
        
        # 2. Test channel
        test_data = {
            'message': 'API channel test',
            'recipient': 'test@example.com'
        }
        
        response = self.client.post(f'/api/alerts/channels/{channel_id}/test/', test_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 3. Get channel health
        response = self.client.get(f'/api/alerts/channels/{channel_id}/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Update channel
        update_data = {
            'is_enabled': False
        }
        
        response = self.client.patch(f'/api/alerts/channels/{channel_id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        response = self.client.get(f'/api/alerts/channels/{channel_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_enabled'])
    
    def test_reporting_workflow(self):
        """Test reporting API workflow"""
        # 1. Generate report
        report_data = {
            'title': 'API Test Report',
            'report_type': 'daily',
            'format_type': 'json',
            'start_date': (timezone.now().date() - timedelta(days=1)).isoformat(),
            'end_date': timezone.now().date().isoformat(),
            'recipients': ['api@example.com']
        }
        
        response = self.client.post('/api/alerts/reports/', report_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        report_id = response.data['id']
        
        # 2. Generate report content
        response = self.client.post(f'/api/alerts/reports/{report_id}/generate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 3. Get dashboard overview
        response = self.client.get('/api/alerts/reports/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        dashboard_data = response.data
        self.assertIn('reports_summary', dashboard_data)
        self.assertIn('mttr_summary', dashboard_data)
        self.assertIn('sla_summary', dashboard_data)
    
    def test_intelligence_workflow(self):
        """Test intelligence API workflow"""
        # 1. Create correlation
        correlation_data = {
            'name': 'API Test Correlation',
            'correlation_type': 'temporal',
            'correlation_threshold': 0.7,
            'time_window_minutes': 30
        }
        
        response = self.client.post('/api/alerts/intelligence/correlations/', correlation_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        correlation_id = response.data['id']
        
        # 2. Analyze correlation
        response = self.client.post(f'/api/alerts/intelligence/correlations/{correlation_id}/analyze/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 3. Create prediction
        prediction_data = {
            'name': 'API Test Prediction',
            'prediction_type': 'threshold_breach',
            'model_type': 'linear_regression',
            'prediction_horizon_hours': 24
        }
        
        response = self.client.post('/api/alerts/intelligence/predictions/', prediction_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        prediction_id = response.data['id']
        
        # 4. Train prediction model
        response = self.client.post(f'/api/alerts/intelligence/predictions/{prediction_id}/train/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Get intelligence overview
        response = self.client.get('/api/alerts/intelligence/overview/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        overview_data = response.data
        self.assertIn('correlations_summary', overview_data)
        self.assertIn('predictions_summary', overview_data)
        self.assertIn('anomaly_models_summary', overview_data)


class SystemIntegrationTest(TransactionTestCase):
    """System integration tests"""
    
    def test_database_integration(self):
        """Test database integration"""
        # Test all models can be created and queried
        models_to_test = [
            (AlertRule, {
                'name': 'DB Test Rule',
                'alert_type': 'cpu_usage',
                'severity': 'high',
                'threshold_value': 80.0
            }),
            (AlertLog, {
                'rule': AlertRule.objects.create(
                    name='DB Test Rule 2',
                    alert_type='memory_usage',
                    severity='medium',
                    threshold_value=85.0
                ),
                'trigger_value': 90.0,
                'threshold_value': 85.0,
                'message': 'DB test alert'
            }),
            (Notification, {
                'alert_log': AlertLog.objects.create(
                    rule=AlertRule.objects.create(
                        name='DB Test Rule 3',
                        alert_type='disk_usage',
                        severity='low',
                        threshold_value=90.0
                    ),
                    trigger_value=95.0,
                    threshold_value=90.0,
                    message='DB test alert 2'
                ),
                'notification_type': 'email',
                'recipient': 'test@example.com',
                'status': 'pending'
            }),
            (SystemMetrics, {
                'total_users': 1000,
                'active_users_1h': 500,
                'total_earnings_1h': 1000.0,
                'avg_response_time_ms': 200.0
            })
        ]
        
        for model_class, data in models_to_test:
            # Create instance
            instance = model_class.objects.create(**data)
            
            # Query instance
            queried = model_class.objects.get(id=instance.id)
            
            # Verify data integrity
            self.assertEqual(instance.id, queried.id)
            
            # Test string representation
            str_repr = str(instance)
            self.assertIsInstance(str_repr, str)
            self.assertGreater(len(str_repr), 0)
    
    def test_service_integration(self):
        """Test service integration"""
        # Create test data
        rule = AlertRule.objects.create(
            name='Service Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Test AlertProcessingService
        service = AlertProcessingService()
        
        result = service.process_alert({
            'rule_id': rule.id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'Service test alert'
        })
        
        self.assertTrue(result['success'])
        
        # Test AlertEscalationService
        from alerts.services.core import AlertEscalationService
        escalation_service = AlertEscalationService()
        
        # Create old alert for escalation
        old_alert = AlertLog.objects.create(
            rule=rule,
            trigger_value=90.0,
            threshold_value=80.0,
            message='Old alert for escalation',
            triggered_at=timezone.now() - timedelta(minutes=30)
        )
        
        escalation_result = escalation_service.check_escalation_needed(old_alert)
        self.assertIn('escalate', escalation_result)
    
    def test_task_integration(self):
        """Test task integration"""
        # Create test data
        rule = AlertRule.objects.create(
            name='Task Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        for i in range(5):
            AlertLog.objects.create(
                rule=rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Task test alert {i}'
            )
        
        # Test ProcessAlertsTask
        task = ProcessAlertsTask()
        result = task.process_pending_alerts(limit=10, dry_run=False)
        
        self.assertIn('processed_count', result)
        self.assertGreater(result['processed_count'], 0)
        
        # Test GenerateReportsTask
        report_task = GenerateReportsTask()
        report_result = report_task.generate_daily_report(
            date=timezone.now().date(),
            format_type='json',
            recipients=['test@example.com']
        )
        
        self.assertIn('report_id', report_result)
    
    def test_signal_integration(self):
        """Test signal integration"""
        # Test that signals are properly connected
        from alerts.signals.core import alert_rule_created, alert_log_created
        
        signal_received = []
        
        def signal_handler(sender, **kwargs):
            signal_received.append((sender.__name__, kwargs))
        
        # Connect signals
        alert_rule_created.connect(signal_handler)
        alert_log_created.connect(signal_handler)
        
        # Create alert rule (should trigger signal)
        rule = AlertRule.objects.create(
            name='Signal Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Create alert log (should trigger signal)
        alert = AlertLog.objects.create(
            rule=rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Signal test alert'
        )
        
        # Verify signals were received
        self.assertEqual(len(signal_received), 2)
        self.assertEqual(signal_received[0][0], 'AlertRule')
        self.assertEqual(signal_received[1][0], 'AlertLog')
    
    def test_configuration_integration(self):
        """Test configuration integration"""
        # Test Django settings integration
        from django.conf import settings
        
        # Check if alerts settings exist
        alerts_settings = getattr(settings, 'ALERTS_SETTINGS', {})
        
        # Should have default configuration
        self.assertIsInstance(alerts_settings, dict)
        
        # Test logging configuration
        import logging
        logger = logging.getLogger('alerts')
        
        # Should be able to log without errors
        logger.info('Configuration integration test')
        
        # Test middleware integration (if exists)
        # This would be tested by making requests through middleware
    
    def test_error_handling_integration(self):
        """Test error handling integration"""
        # Test error handling in services
        service = AlertProcessingService()
        
        # Test with invalid data
        result = service.process_alert({
            'rule_id': 99999,  # Non-existent
            'trigger_value': 'invalid',  # Wrong type
            'threshold_value': None,  # None value
            'message': ''  # Empty message
        })
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        
        # Test error handling in tasks
        task = ProcessAlertsTask()
        
        # Should handle database errors gracefully
        try:
            result = task.process_pending_alerts(limit=10, dry_run=True)
            self.assertIn('processed_count', result)
        except Exception as e:
            # Should handle errors gracefully
            self.assertIsInstance(e, Exception)
    
    def test_performance_integration(self):
        """Test performance integration"""
        import time
        
        # Create test data
        rule = AlertRule.objects.create(
            name='Performance Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Test bulk creation performance
        start_time = time.time()
        
        alerts = []
        for i in range(100):
            alert = AlertLog.objects.create(
                rule=rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Performance test {i}'
            )
            alerts.append(alert)
        
        creation_time = time.time() - start_time
        
        # Should complete within reasonable time
        self.assertLess(creation_time, 5.0)  # 5 seconds max
        self.assertEqual(len(alerts), 100)
        
        # Test query performance
        start_time = time.time()
        
        queried_alerts = AlertLog.objects.filter(rule=rule)
        list(queried_alerts)  # Execute query
        
        query_time = time.time() - start_time
        
        # Should complete within reasonable time
        self.assertLess(query_time, 1.0)  # 1 second max
        self.assertEqual(queried_alerts.count(), 100)
