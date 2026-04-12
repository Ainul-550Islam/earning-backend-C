"""
Tests for Alert URLs
"""
from django.test import TestCase
from django.urls import reverse, resolve
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class AlertURLsTest(TestCase):
    """Test cases for alert URL patterns"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_core_urls_resolve(self):
        """Test core alert URLs resolve correctly"""
        # Alert Rules URLs
        resolve('/api/alerts/rules/')
        resolve('/api/alerts/rules/1/')
        resolve('/api/alerts/rules/1/activate/')
        resolve('/api/alerts/rules/1/deactivate/')
        resolve('/api/alerts/rules/1/test/')
        resolve('/api/alerts/rules/1/statistics/')
        
        # Alert Logs URLs
        resolve('/api/alerts/logs/')
        resolve('/api/alerts/logs/1/')
        resolve('/api/alerts/logs/1/resolve/')
        resolve('/api/alerts/logs/1/acknowledge/')
        resolve('/api/alerts/logs/by_rule/1/')
        resolve('/api/alerts/logs/pending/')
        resolve('/api/alerts/logs/resolved/')
        resolve('/api/alerts/logs/by_severity/high/')
        
        # Notifications URLs
        resolve('/api/alerts/notifications/')
        resolve('/api/alerts/notifications/1/')
        resolve('/api/alerts/notifications/1/mark_sent/')
        resolve('/api/alerts/notifications/1/mark_failed/')
        resolve('/api/alerts/notifications/1/retry/')
        resolve('/api/alerts/notifications/by_status/pending/')
        resolve('/api/alerts/notifications/by_type/email/')
        resolve('/api/alerts/notifications/failed/')
        
        # System Health URLs
        resolve('/api/alerts/health/')
        resolve('/api/alerts/health/metrics/')
        resolve('/api/alerts/health/history/')
        resolve('/api/alerts/health/check/')
        resolve('/api/alerts/health/rules/')
        resolve('/api/alerts/health/channels/')
        resolve('/api/alerts/health/incidents/')
        
        # Overview URLs
        resolve('/api/alerts/overview/')
        resolve('/api/alerts/overview/summary/')
        resolve('/api/alerts/overview/recent_alerts/')
        resolve('/api/alerts/overview/trends/')
        resolve('/api/alerts/overview/top_rules/')
        resolve('/api/alerts/overview/metrics/')
        resolve('/api/alerts/overview/statistics/')
        
        # Maintenance URLs
        resolve('/api/alerts/maintenance/')
        resolve('/api/alerts/maintenance/1/')
        resolve('/api/alerts/maintenance/suppress_alerts/')
        resolve('/api/alerts/maintenance/impact/')
        resolve('/api/alerts/maintenance/1/extend/')
        resolve('/api/alerts/maintenance/1/complete/')
        resolve('/api/alerts/maintenance/history/')
        resolve('/api/alerts/maintenance/upcoming/')
    
    def test_threshold_urls_resolve(self):
        """Test threshold URLs resolve correctly"""
        # Threshold Config URLs
        resolve('/api/alerts/thresholds/configs/')
        resolve('/api/alerts/thresholds/configs/1/')
        resolve('/api/alerts/thresholds/configs/1/evaluate/')
        resolve('/api/alerts/thresholds/configs/1/effectiveness/')
        resolve('/api/alerts/thresholds/configs/1/optimize/')
        
        # Threshold Breach URLs
        resolve('/api/alerts/thresholds/breaches/')
        resolve('/api/alerts/thresholds/breaches/1/')
        resolve('/api/alerts/thresholds/breaches/1/resolve/')
        resolve('/api/alerts/thresholds/breaches/by_severity/high/')
        resolve('/api/alerts/thresholds/breaches/active/')
        resolve('/api/alerts/thresholds/breaches/statistics/')
        resolve('/api/alerts/thresholds/breaches/trends/')
        
        # Adaptive Threshold URLs
        resolve('/api/alerts/thresholds/adaptive/')
        resolve('/api/alerts/thresholds/adaptive/1/')
        resolve('/api/alerts/thresholds/adaptive/1/train/')
        resolve('/api/alerts/thresholds/adaptive/1/adapt/')
        resolve('/api/alerts/thresholds/adaptive/1/history/')
        resolve('/api/alerts/thresholds/adaptive/1/training_status/')
        resolve('/api/alerts/thresholds/adaptive/1/reset/')
        
        # Threshold History URLs
        resolve('/api/alerts/thresholds/history/')
        resolve('/api/alerts/thresholds/history/1/')
        resolve('/api/alerts/thresholds/history/by_type/adaptation/')
        resolve('/api/alerts/thresholds/history/by_adaptive/1/')
        resolve('/api/alerts/thresholds/history/trends/')
        resolve('/api/alerts/thresholds/history/frequency/1/')
        
        # Threshold Profile URLs
        resolve('/api/alerts/thresholds/profiles/')
        resolve('/api/alerts/thresholds/profiles/1/')
        resolve('/api/alerts/thresholds/profiles/1/apply/')
        resolve('/api/alerts/thresholds/profiles/1/thresholds/')
        resolve('/api/alerts/thresholds/profiles/1/mappings/')
        resolve('/api/alerts/thresholds/profiles/1/validate/')
        resolve('/api/alerts/thresholds/profiles/1/clone/')
        resolve('/api/alerts/thresholds/profiles/1/export/')
        resolve('/api/alerts/thresholds/profiles/import/')
    
    def test_channel_urls_resolve(self):
        """Test channel URLs resolve correctly"""
        # Alert Channels URLs
        resolve('/api/alerts/channels/')
        resolve('/api/alerts/channels/1/')
        resolve('/api/alerts/channels/1/enable/')
        resolve('/api/alerts/channels/1/disable/')
        resolve('/api/alerts/channels/1/test/')
        resolve('/api/alerts/channels/1/health/')
        resolve('/api/alerts/channels/1/statistics/')
        
        # Channel Routes URLs
        resolve('/api/alerts/channels/routes/')
        resolve('/api/alerts/channels/routes/1/')
        resolve('/api/alerts/channels/routes/1/activate/')
        resolve('/api/alerts/channels/routes/1/deactivate/')
        resolve('/api/alerts/channels/routes/1/test/')
        resolve('/api/alerts/channels/routes/by_type/escalation/')
        resolve('/api/alerts/channels/routes/active/')
        
        # Channel Health Logs URLs
        resolve('/api/alerts/channels/health_logs/')
        resolve('/api/alerts/channels/health_logs/1/')
        resolve('/api/alerts/channels/health_logs/by_channel/1/')
        resolve('/api/alerts/channels/health_logs/by_status/healthy/')
        resolve('/api/alerts/channels/health_logs/by_type/connectivity/')
        resolve('/api/alerts/channels/health_logs/recent/')
        resolve('/api/alerts/channels/health_logs/statistics/')
        
        # Channel Rate Limits URLs
        resolve('/api/alerts/channels/rate_limits/')
        resolve('/api/alerts/channels/rate_limits/1/')
        resolve('/api/alerts/channels/rate_limits/1/consume_token/')
        resolve('/api/alerts/channels/rate_limits/1/refill_tokens/')
        resolve('/api/alerts/channels/rate_limits/1/reset/')
        resolve('/api/alerts/channels/rate_limits/1/status/')
        resolve('/api/alerts/channels/rate_limits/by_channel/1/')
        resolve('/api/alerts/channels/rate_limits/by_type/per_minute/')
        
        # Alert Recipients URLs
        resolve('/api/alerts/channels/recipients/')
        resolve('/api/alerts/channels/recipients/1/')
        resolve('/api/alerts/channels/recipients/1/activate/')
        resolve('/api/alerts/channels/recipients/1/deactivate/')
        resolve('/api/alerts/channels/recipients/1/test/')
        resolve('/api/alerts/channels/recipients/by_type/user/')
        resolve('/api/alerts/channels/recipients/active/')
        resolve('/api/alerts/channels/recipients/by_priority/1/')
        resolve('/api/alerts/channels/recipients/1/statistics/')
        resolve('/api/alerts/channels/recipients/1/reset_counters/')
    
    def test_incident_urls_resolve(self):
        """Test incident URLs resolve correctly"""
        # Incidents URLs
        resolve('/api/alerts/incidents/')
        resolve('/api/alerts/incidents/1/')
        resolve('/api/alerts/incidents/1/acknowledge/')
        resolve('/api/alerts/incidents/1/identify/')
        resolve('/api/alerts/incidents/1/resolve/')
        resolve('/api/alerts/incidents/1/close/')
        resolve('/api/alerts/incidents/1/escalate/')
        resolve('/api/alerts/incidents/by_severity/high/')
        resolve('/api/alerts/incidents/by_status/open/')
        resolve('/api/alerts/incidents/active/')
        resolve('/api/alerts/incidents/overdue/')
        
        # Incident Timeline URLs
        resolve('/api/alerts/incidents/timelines/')
        resolve('/api/alerts/incidents/timelines/1/')
        resolve('/api/alerts/incidents/timelines/by_incident/1/')
        resolve('/api/alerts/incidents/timelines/by_type/status_change/')
        resolve('/api/alerts/incidents/timelines/1/add_participant/')
        
        # Incident Responders URLs
        resolve('/api/alerts/incidents/responders/')
        resolve('/api/alerts/incidents/responders/1/')
        resolve('/api/alerts/incidents/responders/1/activate/')
        resolve('/api/alerts/incidents/responders/1/deactivate/')
        resolve('/api/alerts/incidents/responders/1/complete/')
        resolve('/api/alerts/incidents/responders/by_incident/1/')
        resolve('/api/alerts/incidents/responders/by_role/responder/')
        
        # Incident Post-Mortem URLs
        resolve('/api/alerts/incidents/postmortems/')
        resolve('/api/alerts/incidents/postmortems/1/')
        resolve('/api/alerts/incidents/postmortems/1/submit_for_review/')
        resolve('/api/alerts/incidents/postmortems/1/approve/')
        resolve('/api/alerts/incidents/postmortems/1/reject/')
        resolve('/api/alerts/incidents/postmortems/1/publish/')
        resolve('/api/alerts/incidents/postmortems/by_status/draft/')
        resolve('/api/alerts/incidents/postmortems/by_incident/1/')
        
        # On-Call Schedule URLs
        resolve('/api/alerts/incidents/oncall_schedules/')
        resolve('/api/alerts/incidents/oncall_schedules/1/')
        resolve('/api/alerts/incidents/oncall_schedules/1/rotate/')
        resolve('/api/alerts/incidents/oncall_schedules/1/current_oncall/')
        resolve('/api/alerts/incidents/oncall_schedules/1/next_rotation/')
        resolve('/api/alerts/incidents/oncall_schedules/1/add_user/')
        resolve('/api/alerts/incidents/oncall_schedules/1/remove_user/')
        resolve('/api/alerts/incidents/oncall_schedules/1/is_oncall/1/')
        resolve('/api/alerts/incidents/oncall_schedules/by_type/rotation/')
        resolve('/api/alerts/incidents/oncall_schedules/active/')
    
    def test_intelligence_urls_resolve(self):
        """Test intelligence URLs resolve correctly"""
        # Alert Correlations URLs
        resolve('/api/alerts/intelligence/correlations/')
        resolve('/api/alerts/intelligence/correlations/1/')
        resolve('/api/alerts/intelligence/correlations/1/analyze/')
        resolve('/api/alerts/intelligence/correlations/1/predict/')
        resolve('/api/alerts/intelligence/correlations/by_type/temporal/')
        resolve('/api/alerts/intelligence/correlations/significant/')
        
        # Alert Predictions URLs
        resolve('/api/alerts/intelligence/predictions/')
        resolve('/api/alerts/intelligence/predictions/1/')
        resolve('/api/alerts/intelligence/predictions/1/train/')
        resolve('/api/alerts/intelligence/predictions/1/predict/')
        resolve('/api/alerts/intelligence/predictions/1/evaluate/')
        resolve('/api/alerts/intelligence/predictions/by_type/threshold_breach/')
        resolve('/api/alerts/intelligence/predictions/active/')
        
        # Anomaly Detection Models URLs
        resolve('/api/alerts/intelligence/anomaly_models/')
        resolve('/api/alerts/intelligence/anomaly_models/1/')
        resolve('/api/alerts/intelligence/anomaly_models/1/detect/')
        resolve('/api/alerts/intelligence/anomaly_models/1/train/')
        resolve('/api/alerts/intelligence/anomaly_models/1/update_thresholds/')
        resolve('/api/alerts/intelligence/anomaly_models/by_method/statistical/')
        resolve('/api/alerts/intelligence/anomaly_models/active/')
        
        # Alert Noise Filters URLs
        resolve('/api/alerts/intelligence/noise_filters/')
        resolve('/api/alerts/intelligence/noise_filters/1/')
        resolve('/api/alerts/intelligence/noise_filters/1/should_filter/')
        resolve('/api/alerts/intelligence/noise_filters/1/filter/')
        resolve('/api/alerts/intelligence/noise_filters/by_type/suppression/')
        resolve('/api/alerts/intelligence/noise_filters/active/')
        resolve('/api/alerts/intelligence/noise_filters/1/effectiveness/')
        
        # Root Cause Analysis URLs
        resolve('/api/alerts/intelligence/rca/')
        resolve('/api/alerts/intelligence/rca/1/')
        resolve('/api/alerts/intelligence/rca/1/analyze/')
        resolve('/api/alerts/intelligence/rca/1/recommendations/')
        resolve('/api/alerts/intelligence/rca/1/submit_for_review/')
        resolve('/api/alerts/intelligence/rca/1/approve/')
        resolve('/api/alerts/intelligence/rca/by_method/5_why/')
        resolve('/api/alerts/intelligence/rca/by_status/completed/')
        
        # Intelligence Integration URLs
        resolve('/api/alerts/intelligence/overview/')
        resolve('/api/alerts/intelligence/metrics/')
        resolve('/api/alerts/intelligence/analyze/')
        resolve('/api/alerts/intelligence/health/')
        resolve('/api/alerts/intelligence/recommendations/')
        resolve('/api/alerts/intelligence/trends/')
    
    def test_reporting_urls_resolve(self):
        """Test reporting URLs resolve correctly"""
        # Alert Reports URLs
        resolve('/api/alerts/reports/')
        resolve('/api/alerts/reports/1/')
        resolve('/api/alerts/reports/1/generate/')
        resolve('/api/alerts/reports/1/distribute/')
        resolve('/api/alerts/reports/1/schedule_next_run/')
        resolve('/api/alerts/reports/by_type/daily/')
        resolve('/api/alerts/reports/by_status/completed/')
        resolve('/api/alerts/reports/recent/')
        resolve('/api/alerts/reports/1/export/')
        
        # MTTR Metrics URLs
        resolve('/api/alerts/reports/mttr/')
        resolve('/api/alerts/reports/mttr/1/')
        resolve('/api/alerts/reports/mttr/1/calculate/')
        resolve('/api/alerts/reports/mttr/1/by_severity/')
        resolve('/api/alerts/reports/mttr/1/trends/')
        resolve('/api/alerts/reports/mttr/1/compliance_badge/')
        resolve('/api/alerts/reports/mttr/by_period/30/')
        
        # MTTD Metrics URLs
        resolve('/api/alerts/reports/mttd/')
        resolve('/api/alerts/reports/mttd/1/')
        resolve('/api/alerts/reports/mttd/1/calculate/')
        resolve('/api/alerts/reports/mttd/1/quality_badge/')
        resolve('/api/alerts/reports/mttd/1/update_rates/')
        
        # SLA Breaches URLs
        resolve('/api/alerts/reports/sla_breaches/')
        resolve('/api/alerts/reports/sla_breaches/1/')
        resolve('/api/alerts/reports/sla_breaches/1/acknowledge/')
        resolve('/api/alerts/reports/sla_breaches/1/resolve/')
        resolve('/api/alerts/reports/sla_breaches/1/escalate/')
        resolve('/api/alerts/reports/sla_breaches/by_severity/critical/')
        resolve('/api/alerts/reports/sla_breaches/by_type/response_time/')
        resolve('/api/alerts/reports/sla_breaches/active/')
        resolve('/api/alerts/reports/sla_breaches/statistics/')
        resolve('/api/alerts/reports/sla_breaches/1/impact_score/')
        
        # Reporting Dashboard URLs
        resolve('/api/alerts/reports/dashboard/')
        resolve('/api/alerts/reports/dashboard/reports_summary/')
        resolve('/api/alerts/reports/dashboard/mttr_summary/')
        resolve('/api/alerts/reports/dashboard/sla_summary/')
        resolve('/api/alerts/reports/dashboard/performance_metrics/')
        resolve('/api/alerts/reports/dashboard/recent_reports/')
        resolve('/api/alerts/reports/dashboard/trending_metrics/')
        resolve('/api/alerts/reports/dashboard/compliance/')
        resolve('/api/alerts/reports/dashboard/export/')


class AlertURLsAPITest(APITestCase):
    """Test cases for alert URL endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_alert_rules_endpoints(self):
        """Test alert rules endpoints"""
        # List alert rules
        url = reverse('alertrule-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Create alert rule
        data = {
            'name': 'Test Alert Rule',
            'alert_type': 'cpu_usage',
            'severity': 'high',
            'threshold_value': 80.0
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        rule_id = response.data['id']
        
        # Retrieve alert rule
        url = reverse('alertrule-detail', kwargs={'pk': rule_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Update alert rule
        data = {'severity': 'critical'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Delete alert rule
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_alert_logs_endpoints(self):
        """Test alert logs endpoints"""
        # List alert logs
        url = reverse('alertlog-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Create alert log (requires a rule first)
        from alerts.models.core import AlertRule
        rule = AlertRule.objects.create(
            name='Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        data = {
            'rule': rule.id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'Test alert'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        log_id = response.data['id']
        
        # Retrieve alert log
        url = reverse('alertlog-detail', kwargs={'pk': log_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Resolve alert log
        resolve_url = reverse('alertlog-resolve', kwargs={'pk': log_id})
        data = {'resolution_note': 'Fixed the issue'}
        response = self.client.post(resolve_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_notifications_endpoints(self):
        """Test notifications endpoints"""
        # List notifications
        url = reverse('notification-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Create notification (requires an alert log first)
        from alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        alert_log = AlertLog.objects.create(
            rule=rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert'
        )
        
        data = {
            'alert_log': alert_log.id,
            'notification_type': 'email',
            'recipient': 'test@example.com',
            'status': 'pending'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        notification_id = response.data['id']
        
        # Retrieve notification
        url = reverse('notification-detail', kwargs={'pk': notification_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Mark notification as sent
        sent_url = reverse('notification-mark-sent', kwargs={'pk': notification_id})
        response = self.client.post(sent_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_system_health_endpoints(self):
        """Test system health endpoints"""
        # Get system health
        url = reverse('systemhealth-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Get health metrics
        metrics_url = reverse('systemhealth-metrics')
        response = self.client.get(metrics_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Run health check
        check_url = reverse('systemhealth-check')
        response = self.client.post(check_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_overview_endpoints(self):
        """Test overview endpoints"""
        # Get overview
        url = reverse('alertoverview-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Get summary
        summary_url = reverse('alertoverview-summary')
        response = self.client.get(summary_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Get recent alerts
        recent_url = reverse('alertoverview-recent-alerts')
        response = self.client.get(recent_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_maintenance_endpoints(self):
        """Test maintenance endpoints"""
        # List maintenance windows
        url = reverse('alertmaintenance-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Create maintenance window
        data = {
            'title': 'Test Maintenance',
            'description': 'Test maintenance window',
            'start_time': timezone.now().isoformat(),
            'end_time': (timezone.now() + timezone.timedelta(hours=2)).isoformat(),
            'maintenance_type': 'scheduled',
            'severity': 'medium'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        maintenance_id = response.data['id']
        
        # Retrieve maintenance window
        detail_url = reverse('alertmaintenance-detail', kwargs={'pk': maintenance_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Complete maintenance window
        complete_url = reverse('alertmaintenance-complete', kwargs={'pk': maintenance_id})
        data = {'completion_note': 'Maintenance completed'}
        response = self.client.post(complete_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_threshold_endpoints(self):
        """Test threshold endpoints"""
        # List threshold configs
        url = reverse('thresholdconfig-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # List threshold breaches
        breaches_url = reverse('thresholdbreach-list')
        response = self.client.get(breaches_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # List adaptive thresholds
        adaptive_url = reverse('adaptivethreshold-list')
        response = self.client.get(adaptive_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_channel_endpoints(self):
        """Test channel endpoints"""
        # List alert channels
        url = reverse('alertchannel-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Create alert channel
        data = {
            'name': 'Test Channel',
            'channel_type': 'email',
            'is_enabled': True,
            'priority': 1
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        channel_id = response.data['id']
        
        # Test channel
        test_url = reverse('alertchannel-test', kwargs={'pk': channel_id})
        data = {'message': 'Test notification', 'recipient': 'test@example.com'}
        response = self.client.post(test_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_incident_endpoints(self):
        """Test incident endpoints"""
        # List incidents
        url = reverse('incident-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Create incident
        data = {
            'title': 'Test Incident',
            'description': 'Test incident description',
            'severity': 'high',
            'impact': 'minor',
            'urgency': 'medium',
            'status': 'open'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        incident_id = response.data['id']
        
        # Acknowledge incident
        ack_url = reverse('incident-acknowledge', kwargs={'pk': incident_id})
        data = {'acknowledgment_note': 'Investigating'}
        response = self.client.post(ack_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_intelligence_endpoints(self):
        """Test intelligence endpoints"""
        # List correlations
        url = reverse('alertcorrelation-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # List predictions
        predictions_url = reverse('alertprediction-list')
        response = self.client.get(predictions_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # List anomaly models
        anomaly_url = reverse('anomalydetectionmodel-list')
        response = self.client.get(anomaly_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Get intelligence overview
        overview_url = reverse('intelligenceintegration-list')
        response = self.client.get(overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_reporting_endpoints(self):
        """Test reporting endpoints"""
        # List reports
        url = reverse('alertreport-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # List MTTR metrics
        mttr_url = reverse('mttrmetric-list')
        response = self.client.get(mttr_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # List SLA breaches
        sla_url = reverse('slabreach-list')
        response = self.client.get(sla_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Get dashboard overview
        dashboard_url = reverse('reportingdashboard-list')
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_unauthorized_access(self):
        """Test unauthorized access to endpoints"""
        self.client.force_authenticate(user=None)
        
        # Should not allow access without authentication
        urls_to_test = [
            reverse('alertrule-list'),
            reverse('alertlog-list'),
            reverse('notification-list'),
            reverse('systemhealth-list'),
            reverse('alertoverview-list')
        ]
        
        for url in urls_to_test:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_url_parameters(self):
        """Test URL parameters and filtering"""
        # Test pagination
        url = reverse('alertrule-list') + '?page=1&page_size=10'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test filtering
        url = reverse('alertrule-list') + '?severity=high&is_active=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test ordering
        url = reverse('alertrule-list') + '?ordering=-created_at'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
