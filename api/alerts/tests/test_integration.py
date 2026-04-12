"""
Integration Tests for Alerts API
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from alerts.models.threshold import ThresholdConfig, ThresholdBreach
from alerts.models.channel import AlertChannel, ChannelRoute
from alerts.models.incident import Incident
from alerts.models.intelligence import AlertCorrelation
from alerts.models.reporting import AlertReport
from alerts.services.core import AlertProcessingService
from alerts.tasks.core import ProcessAlertsTask

User = get_user_model()


class AlertWorkflowIntegrationTest(TransactionTestCase):
    """Integration tests for complete alert workflow"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create alert channel
        self.channel = AlertChannel.objects.create(
            name='Email Channel',
            channel_type='email',
            is_enabled=True,
            config={
                'smtp_server': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_username': 'alerts@example.com'
            }
        )
        
        # Create alert rule
        self.alert_rule = AlertRule.objects.create(
            name='CPU High Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            is_active=True,
            send_email=True
        )
    
    def test_complete_alert_workflow(self):
        """Test complete alert workflow from creation to resolution"""
        # 1. Create alert (trigger)
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high',
            details={'current_usage': 85.0}
        )
        
        # 2. Process alert (should create notifications)
        service = AlertProcessingService()
        result = service.process_alert({
            'rule_id': self.alert_rule.id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'CPU usage is high'
        })
        
        self.assertTrue(result['success'])
        
        # 3. Check notifications were created
        notifications = Notification.objects.filter(alert_log=alert)
        self.assertGreater(notifications.count(), 0)
        
        # 4. Acknowledge alert
        alert.acknowledged_at = timezone.now()
        alert.acknowledgment_note = 'Investigating the issue'
        alert.save()
        
        # 5. Resolve alert
        alert.is_resolved = True
        alert.resolution_note = 'Fixed the CPU issue'
        alert.resolved_at = timezone.now()
        alert.save()
        
        # Verify workflow completion
        alert.refresh_from_db()
        self.assertTrue(alert.is_resolved)
        self.assertIsNotNone(alert.acknowledged_at)
        self.assertIsNotNone(alert.resolved_at)
    
    def test_alert_escalation_workflow(self):
        """Test alert escalation workflow"""
        # Create alert rule with escalation
        escalation_rule = AlertRule.objects.create(
            name='Critical Alert',
            alert_type='system_error',
            severity='critical',
            threshold_value=1.0,
            escalation_enabled=True,
            escalation_delay_minutes=15
        )
        
        # Create old alert that should escalate
        old_alert = AlertLog.objects.create(
            rule=escalation_rule,
            trigger_value=1.0,
            threshold_value=1.0,
            message='Critical system error',
            triggered_at=timezone.now() - timedelta(minutes=30)
        )
        
        # Process escalation
        from alerts.services.core import AlertEscalationService
        escalation_service = AlertEscalationService()
        
        result = escalation_service.check_escalation_needed(old_alert)
        self.assertTrue(result['escalate'])
    
    def test_alert_grouping_workflow(self):
        """Test alert grouping workflow"""
        # Create multiple similar alerts
        base_time = timezone.now() - timedelta(minutes=10)
        alerts = []
        
        for i in range(5):
            alert = AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'CPU usage is high - {i}',
                triggered_at=base_time + timedelta(minutes=i)
            )
            alerts.append(alert)
        
        # Group similar alerts
        from alerts.services.core import AlertGroupService
        grouping_service = AlertGroupService()
        
        groups = grouping_service.group_related_alerts(
            time_window_minutes=15,
            min_group_size=2
        )
        
        self.assertGreater(len(groups), 0)
        
        # Verify grouping logic
        for group in groups:
            self.assertIn('group_id', group)
            self.assertIn('alert_ids', group)
            self.assertGreater(len(group['alert_ids']), 1)


class ThresholdIntegrationTest(TransactionTestCase):
    """Integration tests for threshold management"""
    
    def setUp(self):
        self.alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.threshold_config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='absolute',
            operator='greater_than',
            primary_threshold=85.0,
            secondary_threshold=90.0,
            time_window_minutes=10
        )
    
    def test_threshold_breach_workflow(self):
        """Test threshold breach detection and handling"""
        # Create alert that breaches primary threshold
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=87.0,
            threshold_value=80.0,
            message='CPU usage breaches primary threshold'
        )
        
        # Evaluate threshold condition
        result = self.threshold_config.evaluate_condition(87.0)
        self.assertTrue(result['breached'])
        self.assertEqual(result['breach_level'], 'primary')
        
        # Create threshold breach record
        breach = ThresholdBreach.objects.create(
            threshold_config=self.threshold_config,
            severity='high',
            breach_value=87.0,
            threshold_value=85.0,
            breach_percentage=2.35
        )
        
        # Verify breach creation
        self.assertEqual(breach.breach_value, 87.0)
        self.assertEqual(breach.severity, 'high')
    
    def test_adaptive_threshold_workflow(self):
        """Test adaptive threshold adjustment"""
        from alerts.models.threshold import AdaptiveThreshold
        
        # Create adaptive threshold
        adaptive = AdaptiveThreshold.objects.create(
            threshold_config=self.threshold_config,
            adaptation_method='statistical',
            learning_period_days=30,
            sensitivity=0.8
        )
        
        # Simulate threshold adaptation
        adaptive.adapt_threshold(90.0, 'Increased due to high variability')
        
        # Verify adaptation
        adaptive.refresh_from_db()
        self.assertIsNotNone(adaptive.current_threshold)
        self.assertIsNotNone(adaptive.last_adapted_at)


class ChannelIntegrationTest(TransactionTestCase):
    """Integration tests for notification channels"""
    
    def setUp(self):
        self.source_channel = AlertChannel.objects.create(
            name='Primary Email',
            channel_type='email',
            is_enabled=True
        )
        
        self.backup_channel = AlertChannel.objects.create(
            name='Backup SMS',
            channel_type='sms',
            is_enabled=True
        )
        
        self.channel_route = ChannelRoute.objects.create(
            name='Email to SMS Route',
            route_type='escalation',
            is_active=True,
            escalation_delay_minutes=15
        )
        
        self.channel_route.source_channels.add(self.source_channel)
        self.channel_route.destination_channels.add(self.backup_channel)
    
    def test_channel_routing_workflow(self):
        """Test channel routing for notifications"""
        # Create alert
        alert_rule = AlertRule.objects.create(
            name='Test Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        alert = AlertLog.objects.create(
            rule=alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert'
        )
        
        # Create notification
        notification = Notification.objects.create(
            alert_log=alert,
            notification_type='email',
            recipient='test@example.com',
            status='failed',
            error_message='SMTP server error'
        )
        
        # Test routing logic
        from alerts.services.channel import ChannelRoutingService
        routing_service = ChannelRoutingService()
        
        routing_data = {
            'source_channel_id': self.source_channel.id,
            'notification_data': {
                'recipient': 'test@example.com',
                'subject': 'Test Alert',
                'message': 'Test message'
            }
        }
        
        result = routing_service.route_notification(routing_data)
        self.assertIn('destinations', result)
    
    def test_channel_health_monitoring(self):
        """Test channel health monitoring integration"""
        # Create health logs
        from alerts.models.channel import ChannelHealthLog
        
        for i in range(5):
            ChannelHealthLog.objects.create(
                channel=self.source_channel,
                check_name='connectivity',
                check_type='connectivity',
                status='healthy' if i % 2 == 0 else 'warning',
                response_time_ms=100 + i * 50,
                checked_at=timezone.now() - timedelta(minutes=i * 10)
            )
        
        # Test health service
        from alerts.services.channel import ChannelHealthService
        health_service = ChannelHealthService()
        
        health_result = health_service.check_connectivity(self.source_channel.id)
        self.assertIn('status', health_result)


class IncidentIntegrationTest(TransactionTestCase):
    """Integration tests for incident management"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='incident_user',
            email='incident@example.com',
            password='testpass123'
        )
        
        # Create incident
        self.incident = Incident.objects.create(
            title='Database Connection Failure',
            description='Primary database connection is failing',
            severity='high',
            impact='major',
            urgency='high',
            status='open',
            assigned_to=self.user,
            detected_at=timezone.now()
        )
    
    def test_incident_lifecycle_workflow(self):
        """Test complete incident lifecycle"""
        # 1. Acknowledge incident
        self.incident.acknowledged_at = timezone.now()
        self.incident.acknowledged_by = self.user
        self.incident.acknowledgment_note = 'Investigating database issue'
        self.incident.save()
        
        # 2. Add timeline events
        from alerts.models.incident import IncidentTimeline
        
        timeline1 = IncidentTimeline.objects.create(
            incident=self.incident,
            event_type='status_change',
            title='Incident acknowledged',
            description='Team has acknowledged the incident',
            timestamp=timezone.now(),
            participants=[self.user.id]
        )
        
        # 3. Add responders
        from alerts.models.incident import IncidentResponder
        
        responder = IncidentResponder.objects.create(
            incident=self.incident,
            user=self.user,
            role='lead',
            status='active',
            responsibilities=['Coordination', 'Communication']
        )
        
        # 4. Identify root cause
        self.incident.status = 'identified'
        self.incident.root_cause = 'Database connection pool exhausted'
        self.incident.save()
        
        # 5. Resolve incident
        self.incident.status = 'resolved'
        self.incident.resolved_by = self.user
        self.incident.resolution_note = 'Increased connection pool size'
        self.incident.resolved_at = timezone.now()
        self.incident.save()
        
        # Verify lifecycle completion
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'resolved')
        self.assertIsNotNone(self.incident.acknowledged_at)
        self.assertIsNotNone(self.incident.resolved_at)
    
    def test_incident_post_mortem_workflow(self):
        """Test incident post-mortem workflow"""
        # Set incident as resolved
        self.incident.status = 'resolved'
        self.incident.resolved_at = timezone.now()
        self.incident.save()
        
        # Create post-mortem
        from alerts.models.incident import IncidentPostMortem
        
        post_mortem = IncidentPostMortem.objects.create(
            incident=self.incident,
            title='Database Connection Failure Post-Mortem',
            description='Analysis of database connection failure',
            status='draft',
            created_by=self.user
        )
        
        # Add analysis content
        post_mortem.root_causes = 'Database connection pool exhausted'
        post_mortem.contributing_factors = 'High load, insufficient monitoring'
        post_mortem.lessons_learned = 'Need better connection pool management'
        post_mortem.preventive_measures = 'Increase pool size, add monitoring'
        post_mortem.save()
        
        # Submit for review
        post_mortem.status = 'submitted_for_review'
        post_mortem.reviewed_by = self.user
        post_mortem.reviewed_at = timezone.now()
        post_mortem.save()
        
        # Approve and publish
        post_mortem.status = 'approved'
        post_mortem.approved_by = self.user
        post_mortem.approved_at = timezone.now()
        post_mortem.save()
        
        post_mortem.status = 'published'
        post_mortem.published_at = timezone.now()
        post_mortem.save()
        
        # Verify post-mortem workflow
        post_mortem.refresh_from_db()
        self.assertEqual(post_mortem.status, 'published')
        self.assertIsNotNone(post_mortem.approved_at)
        self.assertIsNotNone(post_mortem.published_at)


class IntelligenceIntegrationTest(TransactionTestCase):
    """Integration tests for intelligence features"""
    
    def setUp(self):
        self.alert_rule1 = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.alert_rule2 = AlertRule.objects.create(
            name='Memory Alert',
            alert_type='memory_usage',
            severity='high',
            threshold_value=85.0
        )
        
        # Create correlated alerts
        base_time = timezone.now() - timedelta(hours=2)
        for i in range(20):
            AlertLog.objects.create(
                rule=self.alert_rule1,
                trigger_value=85.0 + (i % 10),
                threshold_value=80.0,
                message=f'CPU alert {i}',
                triggered_at=base_time + timedelta(minutes=i * 5)
            )
            
            if i % 3 == 0:
                AlertLog.objects.create(
                    rule=self.alert_rule2,
                    trigger_value=90.0 + (i % 8),
                    threshold_value=85.0,
                    message=f'Memory alert {i}',
                    triggered_at=base_time + timedelta(minutes=i * 5 + 2)
                )
    
    def test_correlation_analysis_workflow(self):
        """Test correlation analysis workflow"""
        # Create correlation model
        correlation = AlertCorrelation.objects.create(
            name='CPU-Memory Correlation',
            correlation_type='temporal',
            status='pending',
            correlation_threshold=0.7,
            time_window_minutes=15
        )
        
        correlation.primary_rules.add(self.alert_rule1, self.alert_rule2)
        
        # Analyze correlation
        from alerts.services.intelligence import CorrelationAnalysisService
        correlation_service = CorrelationAnalysisService()
        
        analysis_data = {
            'rule_ids': [self.alert_rule1.id, self.alert_rule2.id],
            'time_window_minutes': 30,
            'correlation_method': 'pearson'
        }
        
        result = correlation_service.analyze_temporal_correlation(analysis_data)
        self.assertIn('correlation_coefficient', result)
        
        # Update correlation model
        if result['correlation_coefficient'] > 0.7:
            correlation.status = 'confirmed'
            correlation.correlation_coefficient = result['correlation_coefficient']
            correlation.confidence_level = result['confidence_level']
            correlation.save()
        
        # Verify correlation analysis
        correlation.refresh_from_db()
        self.assertEqual(correlation.status, 'confirmed')
        self.assertIsNotNone(correlation.correlation_coefficient)
    
    def test_prediction_model_workflow(self):
        """Test prediction model training and usage"""
        from alerts.models.intelligence import AlertPrediction
        
        # Create prediction model
        prediction = AlertPrediction.objects.create(
            name='CPU Usage Prediction',
            prediction_type='threshold_breach',
            model_type='linear_regression',
            training_status='pending',
            prediction_horizon_hours=24
        )
        
        prediction.target_rules.add(self.alert_rule1)
        
        # Train model
        from alerts.services.intelligence import PredictionService
        prediction_service = PredictionService()
        
        training_data = {
            'rule_id': self.alert_rule1.id,
            'model_type': 'linear_regression',
            'features': ['cpu_usage', 'memory_usage'],
            'training_days': 30
        }
        
        result = prediction_service.train_prediction_model(training_data)
        self.assertIn('model_id', result)
        self.assertIn('accuracy_score', result)
        
        # Update model status
        prediction.training_status = 'completed'
        prediction.accuracy_score = result['training_metrics']['accuracy_score']
        prediction.save()
        
        # Test prediction
        prediction_data = {
            'model_id': prediction.id,
            'features': {
                'cpu_usage': 85.0,
                'memory_usage': 70.0
            }
        }
        
        prediction_result = prediction_service.predict_alert_probability(prediction_data)
        self.assertIn('predicted_probability', prediction_result)
    
    def test_anomaly_detection_workflow(self):
        """Test anomaly detection workflow"""
        from alerts.models.intelligence import AnomalyDetectionModel
        
        # Create anomaly detection model
        anomaly_model = AnomalyDetectionModel.objects.create(
            name='CPU Anomaly Detection',
            detection_method='statistical',
            target_rules=self.alert_rule1,
            sensitivity=0.8,
            anomaly_threshold=2.0
        )
        
        # Detect anomalies
        from alerts.services.intelligence import AnomalyDetectionService
        anomaly_service = AnomalyDetectionService()
        
        # Create test data with anomalies
        data_points = []
        for i in range(100):
            value = 50.0 + (i % 10)
            if i % 20 == 0:  # Add anomaly every 20 points
                value = 100.0
            data_points.append(value)
        
        detection_data = {
            'model_id': anomaly_model.id,
            'data_points': data_points
        }
        
        result = anomaly_service.detect_anomalies(detection_data)
        self.assertIn('anomalies', result)
        self.assertGreater(len(result['anomalies']), 0)


class ReportingIntegrationTest(TransactionTestCase):
    """Integration tests for reporting features"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='report_user',
            email='report@example.com',
            password='testpass123'
        )
        
        # Create test data for reports
        for i in range(20):
            alert_rule = AlertRule.objects.create(
                name=f'Alert {i}',
                alert_type='cpu_usage' if i % 2 == 0 else 'memory_usage',
                severity='high' if i % 3 == 0 else 'medium',
                threshold_value=80.0
            )
            
            AlertLog.objects.create(
                rule=alert_rule,
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Alert {i}',
                is_resolved=i % 3 == 0,
                resolved_at=timezone.now() - timedelta(hours=i) if i % 3 == 0 else None
            )
    
    def test_report_generation_workflow(self):
        """Test report generation and distribution"""
        # Create report
        report = AlertReport.objects.create(
            title='Daily Alert Report',
            report_type='daily',
            format_type='json',
            status='pending',
            start_date=timezone.now().date() - timedelta(days=1),
            end_date=timezone.now().date(),
            is_recurring=True,
            created_by=self.user
        )
        
        # Generate report
        from alerts.services.reporting import ReportingService
        reporting_service = ReportingService()
        
        generation_result = reporting_service.generate_report(
            report.id,
            include_summary=True,
            include_details=True,
            include_charts=True
        )
        
        self.assertIn('report_content', generation_result)
        self.assertIn('statistics', generation_result)
        
        # Update report status
        report.status = 'completed'
        report.file_path = generation_result['file_path']
        report.file_size_bytes = generation_result['file_size']
        report.generated_at = timezone.now()
        report.save()
        
        # Distribute report
        distribution_result = reporting_service.distribute_report(
            report.id,
            recipients=['admin@example.com', 'ops@example.com']
        )
        
        self.assertIn('sent_count', distribution_result)
        self.assertIn('failed_count', distribution_result)
        
        # Verify report generation
        report.refresh_from_db()
        self.assertEqual(report.status, 'completed')
        self.assertIsNotNone(report.file_path)
        self.assertIsNotNone(report.generated_at)
    
    def test_metrics_calculation_workflow(self):
        """Test metrics calculation workflow"""
        from alerts.models.reporting import MTTRMetric, MTTDMetric
        
        # Calculate MTTR
        mttr_metric = MTTRMetric.objects.create(
            name='Overall MTTR',
            calculation_period_days=30,
            target_mttr_minutes=60.0,
            created_by=self.user
        )
        
        from alerts.services.reporting import MetricsService
        metrics_service = MetricsService()
        
        mttr_result = metrics_service.calculate_mttr(
            mttr_metric.id,
            start_date=timezone.now().date() - timedelta(days=30),
            end_date=timezone.now().date()
        )
        
        self.assertIn('current_mttr_minutes', mttr_result)
        self.assertIn('alerts_within_target', mttr_result)
        
        # Update MTTR metric
        mttr_metric.current_mttr_minutes = mttr_result['current_mttr_minutes']
        mttr_metric.alerts_within_target = mttr_result['alerts_within_target']
        mttr_metric.target_compliance_percentage = mttr_result['target_compliance_percentage']
        mttr_metric.last_calculated = timezone.now()
        mttr_metric.save()
        
        # Calculate MTTD
        mttd_metric = MTTDMetric.objects.create(
            name='Overall MTTD',
            calculation_period_days=30,
            target_mttd_minutes=15.0,
            created_by=self.user
        )
        
        mttd_result = metrics_service.calculate_mttd(
            mttd_metric.id,
            start_date=timezone.now().date() - timedelta(days=30),
            end_date=timezone.now().date()
        )
        
        self.assertIn('current_mttd_minutes', mttd_result)
        self.assertIn('detection_rate', mttd_result)
        
        # Update MTTD metric
        mttd_metric.current_mttd_minutes = mttd_result['current_mttd_minutes']
        mttd_metric.detection_rate = mttd_result['detection_rate']
        mttd_metric.false_positive_rate = mttd_result['false_positive_rate']
        mttd_metric.last_calculated = timezone.now()
        mttd_metric.save()


class APIIntegrationTest(APITestCase):
    """Integration tests for API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_alert_management_api_workflow(self):
        """Test complete alert management API workflow"""
        # 1. Create alert rule
        rule_data = {
            'name': 'API Test Alert',
            'alert_type': 'cpu_usage',
            'severity': 'high',
            'threshold_value': 80.0,
            'description': 'API test alert rule'
        }
        
        response = self.client.post('/api/alerts/rules/', rule_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        rule_id = response.data['id']
        
        # 2. Create alert log
        alert_data = {
            'rule': rule_id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'API test alert'
        }
        
        response = self.client.post('/api/alerts/logs/', alert_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        alert_id = response.data['id']
        
        # 3. Acknowledge alert
        ack_data = {
            'acknowledgment_note': 'Investigating via API'
        }
        
        response = self.client.post(f'/api/alerts/logs/{alert_id}/acknowledge/', ack_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Resolve alert
        resolve_data = {
            'resolution_note': 'Fixed via API'
        }
        
        response = self.client.post(f'/api/alerts/logs/{alert_id}/resolve/', resolve_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Verify final state
        response = self.client.get(f'/api/alerts/logs/{alert_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_resolved'])
        self.assertIsNotNone(response.data['acknowledged_at'])
        self.assertIsNotNone(response.data['resolved_at'])
    
    def test_channel_management_api_workflow(self):
        """Test channel management API workflow"""
        # 1. Create channel
        channel_data = {
            'name': 'API Test Channel',
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
        self.assertIn('health_status', response.data)
    
    def test_incident_management_api_workflow(self):
        """Test incident management API workflow"""
        # 1. Create incident
        incident_data = {
            'title': 'API Test Incident',
            'description': 'Test incident via API',
            'severity': 'high',
            'impact': 'minor',
            'urgency': 'medium',
            'status': 'open'
        }
        
        response = self.client.post('/api/alerts/incidents/', incident_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        incident_id = response.data['id']
        
        # 2. Acknowledge incident
        ack_data = {
            'acknowledgment_note': 'Acknowledged via API'
        }
        
        response = self.client.post(f'/api/alerts/incidents/{incident_id}/acknowledge/', ack_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 3. Add timeline event
        timeline_data = {
            'event_type': 'action',
            'title': 'Investigation started',
            'description': 'Started investigation via API'
        }
        
        response = self.client.post('/api/alerts/incidents/timelines/', {
            'incident': incident_id,
            **timeline_data
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 4. Resolve incident
        resolve_data = {
            'resolution_summary': 'Resolved via API',
            'resolution_actions': 'API test actions'
        }
        
        response = self.client.post(f'/api/alerts/incidents/{incident_id}/resolve/', resolve_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_reporting_api_workflow(self):
        """Test reporting API workflow"""
        # 1. Generate daily report
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
        self.assertIn('report_id', response.data)
        
        # 3. Get dashboard overview
        response = self.client.get('/api/alerts/reports/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reports_summary', response.data)
        self.assertIn('mttr_summary', response.data)
        self.assertIn('sla_summary', response.data)


class SystemIntegrationTest(TransactionTestCase):
    """Integration tests for system-wide features"""
    
    def test_task_processing_integration(self):
        """Test task processing integration"""
        # Create alert rule and alerts
        alert_rule = AlertRule.objects.create(
            name='Task Test Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            is_active=True
        )
        
        for i in range(5):
            AlertLog.objects.create(
                rule=alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Task test alert {i}'
            )
        
        # Run processing task
        task = ProcessAlertsTask()
        result = task.process_pending_alerts(limit=10, dry_run=False)
        
        self.assertIn('processed_count', result)
        self.assertGreater(result['processed_count'], 0)
    
    def test_system_health_integration(self):
        """Test system health monitoring integration"""
        # Create test data
        for i in range(5):
            AlertRule.objects.create(
                name=f'Health Test {i}',
                alert_type='cpu_usage',
                severity='high' if i % 2 == 0 else 'medium',
                threshold_value=80.0,
                is_active=i % 3 != 0
            )
        
        for i in range(3):
            SystemMetrics.objects.create(
                total_users=1000 + i * 100,
                active_users_1h=500 + i * 50,
                total_earnings_1h=1000.0 + i * 100,
                avg_response_time_ms=200.0 + i * 20
            )
        
        # Run health check
        from alerts.tasks.core import CheckHealthTask
        health_task = CheckHealthTask()
        
        result = health_task.check_alert_system_health(time_period_hours=24)
        self.assertIn('overall_health', result)
        self.assertIn('alerts_health', result)
    
    def test_data_cleanup_integration(self):
        """Test data cleanup integration"""
        # Create old data
        old_date = timezone.now() - timedelta(days=100)
        
        for i in range(10):
            AlertLog.objects.create(
                rule=AlertRule.objects.create(
                    name=f'Cleanup Test {i}',
                    alert_type='cpu_usage',
                    severity='medium',
                    threshold_value=80.0
                ),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Old alert {i}',
                triggered_at=old_date
            )
        
        # Run cleanup task
        from alerts.tasks.core import CleanupAlertsTask
        cleanup_task = CleanupAlertsTask()
        
        initial_count = AlertLog.objects.count()
        result = cleanup_task.cleanup_old_alerts(days=90, dry_run=False)
        
        self.assertIn('deleted_count', result)
        self.assertLess(AlertLog.objects.count(), initial_count)
