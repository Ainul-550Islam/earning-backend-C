"""
Enhanced Security Insight Tests
Comprehensive test suite for security insight functionality
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

from ..services.SecurityInsightService import SecurityInsightService
from .factories import (
    UserFactory, StaffUserFactory, SecurityInsightFactory,
    SecurityLogFactory, UserBanFactory, IPBlacklistFactory
)


class SecurityInsightServiceTest(TestCase):
    """Test SecurityInsightService class"""
    
    def setUp(self):
        self.service = SecurityInsightService()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        cache.clear()
    
    def test_security_insight_service_initialization(self):
        """Test SecurityInsightService initialization"""
        self.assertIsNotNone(self.service.cache_manager)
        self.assertIsNotNone(self.service.logger)
        self.assertIsNotNone(self.service.default_cache_timeout)
        self.assertIsNotNone(self.service.insight_cache_prefix)
    
    def test_security_insight_service_default_config(self):
        """Test default configuration"""
        self.assertEqual(self.service.default_cache_timeout, 3600)
        self.assertEqual(self.service.insight_cache_prefix, "security_insight")
    
    def test_get_insight_by_date(self):
        """Test getting insight by date"""
        test_date = timezone.now().date()
        
        with patch('api.security.models.SecurityInsight.objects.filter') as mock_filter:
            mock_insight = SecurityInsightFactory(
                insight_date=test_date,
                total_security_events=100,
                high_risk_events=10,
                vpn_detections=5,
                proxy_detections=3,
                failed_logins=20,
                successful_logins=200,
                unique_ips=50,
                top_threat_types={'malware': 3, 'phishing': 2},
                risk_distribution={'low': 60, 'medium': 25, 'high': 12, 'critical': 3}
            )
            mock_queryset = MagicMock()
            mock_queryset.first.return_value = mock_insight
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_insight_by_date(test_date)
            
            self.assertEqual(result['insight_date'], test_date)
            self.assertEqual(result['total_security_events'], 100)
            self.assertEqual(result['high_risk_events'], 10)
            self.assertEqual(result['vpn_detections'], 5)
    
    def test_get_insight_by_date_cached(self):
        """Test getting cached insight by date"""
        test_date = timezone.now().date()
        cache_key = f"{self.service.insight_cache_prefix}:date:{test_date}"
        cached_insight = {
            'insight_date': test_date,
            'total_security_events': 100,
            'high_risk_events': 10
        }
        cache.set(cache_key, cached_insight, self.service.default_cache_timeout)
        
        result = self.service.get_insight_by_date(test_date)
        
        self.assertEqual(result['total_security_events'], 100)
        self.assertEqual(result['high_risk_events'], 10)
    
    def test_get_insight_by_date_not_found(self):
        """Test getting non-existent insight by date"""
        test_date = timezone.now().date()
        
        with patch('api.security.models.SecurityInsight.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.first.return_value = None
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_insight_by_date(test_date)
            
            self.assertIsNone(result)
    
    def test_get_insight_by_date_range(self):
        """Test getting insights by date range"""
        start_date = timezone.now().date() - timezone.timedelta(days=7)
        end_date = timezone.now().date()
        
        with patch('api.security.models.SecurityInsight.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 7
            mock_queryset.order_by.return_value = [
                SecurityInsightFactory(),
                SecurityInsightFactory(),
                SecurityInsightFactory()
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_insight_by_date_range(start_date, end_date)
            
            self.assertEqual(result['count'], 7)
            self.assertEqual(len(result['insights']), 3)
    
    def test_create_daily_insight(self):
        """Test creating daily insight"""
        insight_date = timezone.now().date()
        
        with patch.object(self.service, '_calculate_daily_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'total_security_events': 150,
                'high_risk_events': 15,
                'vpn_detections': 8,
                'proxy_detections': 4,
                'failed_logins': 25,
                'successful_logins': 250,
                'unique_ips': 75,
                'top_threat_types': {'malware': 5, 'phishing': 3},
                'risk_distribution': {'low': 55, 'medium': 30, 'high': 12, 'critical': 3}
            }
            
            with patch('api.security.models.SecurityInsight.objects.create') as mock_create:
                mock_insight = MagicMock()
                mock_insight.id = 'insight-id'
                mock_create.return_value = mock_insight
                
                result = self.service.create_daily_insight(insight_date)
                
                self.assertEqual(result, mock_insight)
                mock_create.assert_called_once()
    
    def test_calculate_daily_metrics(self):
        """Test calculating daily metrics"""
        insight_date = timezone.now().date()
        
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 100
            mock_filter.return_value = mock_queryset
            
            with patch.object(self.service, '_get_top_threat_types') as mock_threats:
                mock_threats.return_value = {'malware': 5, 'phishing': 3}
                
                with patch.object(self.service, '_calculate_risk_distribution') as mock_risk:
                    mock_risk.return_value = {'low': 60, 'medium': 25, 'high': 12, 'critical': 3}
                    
                    metrics = self.service._calculate_daily_metrics(insight_date)
                    
                    self.assertEqual(metrics['total_security_events'], 100)
                    self.assertIn('top_threat_types', metrics)
                    self.assertIn('risk_distribution', metrics)
    
    def test_get_top_threat_types(self):
        """Test getting top threat types"""
        insight_date = timezone.now().date()
        
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value.annotate.return_value.order_by.return_value = [
                {'event_type': 'malware_detected', 'count': 15},
                {'event_type': 'phishing_attempt', 'count': 10},
                {'event_type': 'suspicious_login', 'count': 8}
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service._get_top_threat_types(insight_date)
            
            self.assertEqual(result['malware'], 15)
            self.assertEqual(result['phishing'], 10)
            self.assertEqual(result['suspicious_login'], 8)
    
    def test_calculate_risk_distribution(self):
        """Test calculating risk distribution"""
        insight_date = timezone.now().date()
        
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value.annotate.return_value = [
                {'severity': 'debug', 'count': 10},
                {'severity': 'info', 'count': 20},
                {'severity': 'warning', 'count': 15},
                {'severity': 'error', 'count': 8},
                {'severity': 'critical', 'count': 3},
                {'severity': 'security', 'count': 4}
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service._calculate_risk_distribution(insight_date)
            
            self.assertEqual(result['low'], 30)  # debug + info
            self.assertEqual(result['medium'], 15)  # warning
            self.assertEqual(result['high'], 12)   # error + security
            self.assertEqual(result['critical'], 3)  # critical
    
    def test_get_security_trends(self):
        """Test getting security trends"""
        with patch.object(self.service, '_calculate_security_trends') as mock_trends:
            mock_trends.return_value = [
                {
                    'date': '2023-01-01',
                    'total_events': 100,
                    'high_risk_events': 10,
                    'trend_direction': 'stable'
                },
                {
                    'date': '2023-01-02',
                    'total_events': 120,
                    'high_risk_events': 15,
                    'trend_direction': 'increasing'
                }
            ]
            
            result = self.service.get_security_trends(days=30)
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['total_events'], 100)
            self.assertEqual(result[1]['trend_direction'], 'increasing')
    
    def test_calculate_security_trends(self):
        """Test calculating security trends"""
        with patch('api.security.models.SecurityInsight.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.order_by.return_value = [
                SecurityInsightFactory(
                    insight_date=timezone.now().date() - timezone.timedelta(days=2),
                    total_security_events=100,
                    high_risk_events=10
                ),
                SecurityInsightFactory(
                    insight_date=timezone.now().date() - timezone.timedelta(days=1),
                    total_security_events=120,
                    high_risk_events=15
                )
            ]
            mock_filter.return_value = mock_queryset
            
            trends = self.service._calculate_security_trends(days=30)
            
            self.assertIsInstance(trends, list)
            self.assertGreater(len(trends), 0)
    
    def test_get_threat_intelligence_insights(self):
        """Test getting threat intelligence insights"""
        with patch.object(self.service, '_analyze_threat_intelligence') as mock_analysis:
            mock_analysis.return_value = {
                'total_threats': 50,
                'active_threats': 35,
                'threat_types': {
                    'malware': 20,
                    'phishing': 15,
                    'botnet': 10,
                    'ddos': 5
                },
                'severity_distribution': {
                    'low': 10,
                    'medium': 20,
                    'high': 15,
                    'critical': 5
                },
                'trending_threats': [
                    {'threat_type': 'malware', 'trend': 'increasing', 'change': '+25%'},
                    {'threat_type': 'phishing', 'trend': 'stable', 'change': '0%'}
                ]
            }
            
            result = self.service.get_threat_intelligence_insights(days=30)
            
            self.assertEqual(result['total_threats'], 50)
            self.assertEqual(result['active_threats'], 35)
            self.assertIn('threat_types', result)
            self.assertIn('severity_distribution', result)
    
    def test_analyze_threat_intelligence(self):
        """Test analyzing threat intelligence"""
        with patch('api.security.models.ThreatIntelligence.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 50
            mock_queryset.filter.return_value.count.return_value = 35
            mock_queryset.values.return_value.annotate.return_value = [
                {'threat_type': 'malware', 'count': 20},
                {'threat_type': 'phishing', 'count': 15}
            ]
            mock_filter.return_value = mock_queryset
            
            analysis = self.service._analyze_threat_intelligence(days=30)
            
            self.assertIn('total_threats', analysis)
            self.assertIn('active_threats', analysis)
            self.assertIn('threat_types', analysis)
    
    def test_get_user_behavior_insights(self):
        """Test getting user behavior insights"""
        with patch.object(self.service, '_analyze_user_behavior') as mock_analysis:
            mock_analysis.return_value = {
                'total_active_users': 1000,
                'suspicious_users': 25,
                'high_risk_users': 10,
                'behavior_patterns': {
                    'normal_users': 950,
                    'suspicious_users': 40,
                    'high_risk_users': 10
                },
                'anomaly_detection': {
                    'unusual_login_patterns': 15,
                    'strange_access_times': 8,
                    'suspicious_locations': 5
                },
                'risk_factors': [
                    {'factor': 'multiple_ip_addresses', 'affected_users': 30},
                    {'factor': 'unusual_access_hours', 'affected_users': 15}
                ]
            }
            
            result = self.service.get_user_behavior_insights(days=30)
            
            self.assertEqual(result['total_active_users'], 1000)
            self.assertEqual(result['suspicious_users'], 25)
            self.assertIn('behavior_patterns', result)
            self.assertIn('anomaly_detection', result)
    
    def test_analyze_user_behavior(self):
        """Test analyzing user behavior"""
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value.annotate.return_value = [
                {'user_id': self.user.id, 'event_count': 50, 'unique_ips': 3},
                {'user_id': self.staff_user.id, 'event_count': 25, 'unique_ips': 1}
            ]
            mock_filter.return_value = mock_queryset
            
            analysis = self.service._analyze_user_behavior(days=30)
            
            self.assertIn('total_active_users', analysis)
            self.assertIn('suspicious_users', analysis)
            self.assertIn('behavior_patterns', analysis)
    
    def test_get_network_security_insights(self):
        """Test getting network security insights"""
        with patch.object(self.service, '_analyze_network_security') as mock_analysis:
            mock_analysis.return_value = {
                'total_unique_ips': 500,
                'suspicious_ips': 25,
                'blocked_ips': 15,
                'geographic_distribution': {
                    'US': 200,
                    'EU': 150,
                    'Asia': 100,
                    'Other': 50
                },
                'ip_reputation': {
                    'clean': 450,
                    'suspicious': 35,
                    'malicious': 15
                },
                'vpn_proxy_usage': {
                    'vpn_detected': 20,
                    'proxy_detected': 10,
                    'tor_usage': 5
                }
            }
            
            result = self.service.get_network_security_insights(days=30)
            
            self.assertEqual(result['total_unique_ips'], 500)
            self.assertEqual(result['suspicious_ips'], 25)
            self.assertIn('geographic_distribution', result)
            self.assertIn('ip_reputation', result)
    
    def test_analyze_network_security(self):
        """Test analyzing network security"""
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value.annotate.return_value = [
                {'ip_address': '192.168.1.1', 'event_count': 50, 'country': 'US'},
                {'ip_address': '192.168.1.2', 'event_count': 25, 'country': 'EU'}
            ]
            mock_filter.return_value = mock_queryset
            
            analysis = self.service._analyze_network_security(days=30)
            
            self.assertIn('total_unique_ips', analysis)
            self.assertIn('suspicious_ips', analysis)
            self.assertIn('geographic_distribution', analysis)
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        with patch.object(self.service, '_calculate_performance_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'response_time_avg': 150.5,
                'response_time_p95': 300.0,
                'throughput_per_second': 1000,
                'error_rate': 0.02,
                'availability': 99.95,
                'resource_utilization': {
                    'cpu': 65.5,
                    'memory': 70.2,
                    'disk': 45.8
                }
            }
            
            result = self.service.get_performance_metrics(days=30)
            
            self.assertEqual(result['response_time_avg'], 150.5)
            self.assertEqual(result['throughput_per_second'], 1000)
            self.assertEqual(result['error_rate'], 0.02)
            self.assertIn('resource_utilization', result)
    
    def test_calculate_performance_metrics(self):
        """Test calculating performance metrics"""
        metrics = self.service._calculate_performance_metrics(days=30)
        
        self.assertIn('response_time_avg', metrics)
        self.assertIn('response_time_p95', metrics)
        self.assertIn('throughput_per_second', metrics)
        self.assertIn('error_rate', metrics)
        self.assertIn('availability', metrics)
        self.assertIn('resource_utilization', metrics)
    
    def test_get_compliance_insights(self):
        """Test getting compliance insights"""
        with patch.object(self.service, '_analyze_compliance') as mock_analysis:
            mock_analysis.return_value = {
                'overall_compliance_score': 85.5,
                'policy_compliance': {
                    'password_policy': 90.0,
                    'session_policy': 80.0,
                    'access_policy': 88.0
                },
                'violations': {
                    'total_violations': 25,
                    'high_priority_violations': 5,
                    'violation_trends': 'decreasing'
                },
                'audit_trail': {
                    'total_audits': 100,
                    'passed_audits': 85,
                    'failed_audits': 15
                }
            }
            
            result = self.service.get_compliance_insights(days=30)
            
            self.assertEqual(result['overall_compliance_score'], 85.5)
            self.assertEqual(result['violations']['total_violations'], 25)
            self.assertIn('policy_compliance', result)
            self.assertIn('audit_trail', result)
    
    def test_analyze_compliance(self):
        """Test analyzing compliance"""
        with patch('api.security.models.PolicyAuditLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 100
            mock_queryset.filter.return_value.count.return_value = 85
            mock_filter.return_value = mock_queryset
            
            analysis = self.service._analyze_compliance(days=30)
            
            self.assertIn('overall_compliance_score', analysis)
            self.assertIn('policy_compliance', analysis)
            self.assertIn('violations', analysis)
    
    def test_get_risk_assessment_insights(self):
        """Test getting risk assessment insights"""
        with patch.object(self.service, '_analyze_risk_assessment') as mock_analysis:
            mock_analysis.return_value = {
                'overall_risk_score': 45.5,
                'risk_level': 'medium',
                'risk_categories': {
                    'operational_risk': 30.0,
                    'security_risk': 55.0,
                    'compliance_risk': 25.0,
                    'reputational_risk': 20.0
                },
                'high_risk_assets': [
                    {'asset': 'user_database', 'risk_score': 75.0},
                    {'asset': 'api_endpoints', 'risk_score': 60.0}
                ],
                'mitigation_recommendations': [
                    'Implement additional security controls',
                    'Increase monitoring frequency'
                ]
            }
            
            result = self.service.get_risk_assessment_insights(days=30)
            
            self.assertEqual(result['overall_risk_score'], 45.5)
            self.assertEqual(result['risk_level'], 'medium')
            self.assertIn('risk_categories', result)
            self.assertIn('high_risk_assets', result)
    
    def test_analyze_risk_assessment(self):
        """Test analyzing risk assessment"""
        with patch('api.security.models.RiskScore.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.aggregate.return_value = {
                'avg_score': 45.5,
                'max_score': 85.0,
                'min_score': 15.0
            }
            mock_filter.return_value = mock_queryset
            
            analysis = self.service._analyze_risk_assessment(days=30)
            
            self.assertIn('overall_risk_score', analysis)
            self.assertIn('risk_level', analysis)
            self.assertIn('risk_categories', analysis)
    
    def test_get_incident_insights(self):
        """Test getting incident insights"""
        with patch.object(self.service, '_analyze_incidents') as mock_analysis:
            mock_analysis.return_value = {
                'total_incidents': 25,
                'active_incidents': 5,
                'resolved_incidents': 20,
                'incident_types': {
                    'security_breach': 10,
                    'data_leak': 5,
                    'system_compromise': 8,
                    'policy_violation': 2
                },
                'severity_distribution': {
                    'low': 8,
                    'medium': 10,
                    'high': 5,
                    'critical': 2
                },
                'resolution_metrics': {
                    'avg_resolution_time': 48.5,
                    'resolution_rate': 80.0
                }
            }
            
            result = self.service.get_incident_insights(days=30)
            
            self.assertEqual(result['total_incidents'], 25)
            self.assertEqual(result['active_incidents'], 5)
            self.assertIn('incident_types', result)
            self.assertIn('resolution_metrics', result)
    
    def test_analyze_incidents(self):
        """Test analyzing incidents"""
        with patch('api.security.models.SecurityIncident.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 25
            mock_queryset.filter.return_value.count.return_value = 5
            mock_queryset.values.return_value.annotate.return_value = [
                {'incident_type': 'security_breach', 'count': 10},
                {'incident_type': 'data_leak', 'count': 5}
            ]
            mock_filter.return_value = mock_queryset
            
            analysis = self.service._analyze_incidents(days=30)
            
            self.assertIn('total_incidents', analysis)
            self.assertIn('active_incidents', analysis)
            self.assertIn('incident_types', analysis)
    
    def test_get_forecast_insights(self):
        """Test getting forecast insights"""
        with patch.object(self.service, '_generate_forecasts') as mock_forecasts:
            mock_forecasts.return_value = {
                'security_events_forecast': {
                    'next_7_days': 350,
                    'next_30_days': 1500,
                    'trend_direction': 'increasing',
                    'confidence_level': 0.85
                },
                'risk_forecast': {
                    'risk_level': 'medium',
                    'probability_increase': 0.15,
                    'key_factors': ['seasonal_patterns', 'new_threats']
                },
                'resource_forecast': {
                    'expected_load_increase': 0.25,
                    'recommended_scaling': 'moderate'
                }
            }
            
            result = self.service.get_forecast_insights(days=30)
            
            self.assertEqual(result['security_events_forecast']['next_7_days'], 350)
            self.assertEqual(result['risk_forecast']['risk_level'], 'medium')
            self.assertIn('resource_forecast', result)
    
    def test_generate_forecasts(self):
        """Test generating forecasts"""
        forecasts = self.service._generate_forecasts(days=30)
        
        self.assertIn('security_events_forecast', forecasts)
        self.assertIn('risk_forecast', forecasts)
        self.assertIn('resource_forecast', forecasts)
    
    def test_get_anomaly_insights(self):
        """Test getting anomaly insights"""
        with patch.object(self.service, '_detect_anomalies') as mock_anomalies:
            mock_anomalies.return_value = {
                'total_anomalies': 15,
                'anomaly_types': {
                    'statistical_anomaly': 8,
                    'behavioral_anomaly': 5,
                    'network_anomaly': 2
                },
                'severity_distribution': {
                    'low': 5,
                    'medium': 7,
                    'high': 3
                },
                'affected_systems': [
                    {'system': 'authentication', 'anomaly_count': 6},
                    {'system': 'authorization', 'anomaly_count': 4}
                ],
                'recommendations': [
                    'Investigate authentication anomalies',
                    'Review system logs for patterns'
                ]
            }
            
            result = self.service.get_anomaly_insights(days=30)
            
            self.assertEqual(result['total_anomalies'], 15)
            self.assertEqual(result['anomaly_types']['statistical_anomaly'], 8)
            self.assertIn('affected_systems', result)
    
    def test_detect_anomalies(self):
        """Test detecting anomalies"""
        anomalies = self.service._detect_anomalies(days=30)
        
        self.assertIn('total_anomalies', anomalies)
        self.assertIn('anomaly_types', anomalies)
        self.assertIn('severity_distribution', anomalies)
    
    def test_get_kpi_insights(self):
        """Test getting KPI insights"""
        with patch.object(self.service, '_calculate_kpis') as mock_kpis:
            mock_kpis.return_value = {
                'security_posture_score': 85.5,
                'threat_detection_rate': 92.0,
                'incident_response_time': 2.5,
                'compliance_rate': 88.0,
                'user_satisfaction': 85.0,
                'cost_per_security_event': 150.0,
                'kpi_trends': {
                    'security_posture': 'improving',
                    'threat_detection': 'stable',
                    'incident_response': 'improving'
                }
            }
            
            result = self.service.get_kpi_insights(days=30)
            
            self.assertEqual(result['security_posture_score'], 85.5)
            self.assertEqual(result['threat_detection_rate'], 92.0)
            self.assertEqual(result['incident_response_time'], 2.5)
            self.assertIn('kpi_trends', result)
    
    def test_calculate_kpis(self):
        """Test calculating KPIs"""
        kpis = self.service._calculate_kpis(days=30)
        
        self.assertIn('security_posture_score', kpis)
        self.assertIn('threat_detection_rate', kpis)
        self.assertIn('incident_response_time', kpis)
        self.assertIn('compliance_rate', kpis)
        self.assertIn('user_satisfaction', kpis)
        self.assertIn('cost_per_security_event', kpis)
    
    def test_get_executive_summary(self):
        """Test getting executive summary"""
        with patch.object(self.service, '_generate_executive_summary') as mock_summary:
            mock_summary.return_value = {
                'overall_security_status': 'healthy',
                'key_metrics': {
                    'security_score': 85.5,
                    'threat_level': 'medium',
                    'compliance_rate': 88.0
                },
                'highlights': [
                    'Security incidents decreased by 15%',
                    'Compliance rate improved by 5%',
                    'Threat detection rate at 92%'
                ],
                'concerns': [
                    'Increase in sophisticated attacks',
                    'Resource constraints in security team'
                ],
                'recommendations': [
                    'Invest in advanced threat detection',
                    'Expand security team capabilities'
                ]
            }
            
            result = self.service.get_executive_summary(days=30)
            
            self.assertEqual(result['overall_security_status'], 'healthy')
            self.assertEqual(result['key_metrics']['security_score'], 85.5)
            self.assertIn('highlights', result)
            self.assertIn('concerns', result)
            self.assertIn('recommendations', result)
    
    def test_generate_executive_summary(self):
        """Test generating executive summary"""
        summary = self.service._generate_executive_summary(days=30)
        
        self.assertIn('overall_security_status', summary)
        self.assertIn('key_metrics', summary)
        self.assertIn('highlights', summary)
        self.assertIn('concerns', summary)
        self.assertIn('recommendations', summary)
    
    def test_get_detailed_insights(self):
        """Test getting detailed insights"""
        with patch.object(self.service, '_generate_detailed_insights') as mock_insights:
            mock_insights.return_value = {
                'security_events': {
                    'total_events': 1500,
                    'event_breakdown': {
                        'authentication': 500,
                        'authorization': 300,
                        'data_access': 400,
                        'system_events': 300
                    },
                    'trend_analysis': 'stable'
                },
                'threat_landscape': {
                    'active_threats': 35,
                    'threat_intelligence': {
                        'new_threats': 5,
                        'evolving_threats': 10,
                        'stable_threats': 20
                    }
                },
                'user_behavior': {
                    'active_users': 1000,
                    'behavior_patterns': {
                        'normal': 950,
                        'suspicious': 40,
                        'malicious': 10
                    }
                },
                'system_performance': {
                    'availability': 99.95,
                    'response_time': 150.5,
                    'throughput': 1000
                }
            }
            
            result = self.service.get_detailed_insights(days=30)
            
            self.assertEqual(result['security_events']['total_events'], 1500)
            self.assertEqual(result['threat_landscape']['active_threats'], 35)
            self.assertIn('user_behavior', result)
            self.assertIn('system_performance', result)
    
    def test_generate_detailed_insights(self):
        """Test generating detailed insights"""
        insights = self.service._generate_detailed_insights(days=30)
        
        self.assertIn('security_events', insights)
        self.assertIn('threat_landscape', insights)
        self.assertIn('user_behavior', insights)
        self.assertIn('system_performance', insights)
    
    def test_export_insights(self):
        """Test exporting insights"""
        with patch.object(self.service, '_prepare_export_data') as mock_export:
            mock_export.return_value = {
                'summary': {
                    'period': '30 days',
                    'total_events': 1500,
                    'security_score': 85.5
                },
                'detailed_data': {
                    'daily_insights': [
                        {'date': '2023-01-01', 'events': 50},
                        {'date': '2023-01-02', 'events': 55}
                    ],
                    'threat_analysis': {},
                    'user_behavior': {}
                }
            }
            
            result = self.service.export_insights(
                days=30,
                format='json'
            )
            
            self.assertEqual(result['summary']['total_events'], 1500)
            self.assertEqual(result['summary']['security_score'], 85.5)
            self.assertIn('detailed_data', result)
    
    def test_export_insights_csv(self):
        """Test exporting insights in CSV format"""
        with patch.object(self.service, '_prepare_export_data') as mock_export:
            mock_export.return_value = {
                'summary': {
                    'period': '30 days',
                    'total_events': 1500,
                    'security_score': 85.5
                }
            }
            
            result = self.service.export_insights(
                days=30,
                format='csv'
            )
            
            self.assertIn('period', result)
            self.assertIn('total_events', result)
            self.assertIn('security_score', result)
    
    def test_get_real_time_insights(self):
        """Test getting real-time insights"""
        with patch.object(self.service, '_calculate_real_time_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'current_events_per_minute': 5.5,
                'active_threats': 3,
                'system_load': 65.5,
                'response_time_current': 145.0,
                'anomaly_count': 2,
                'alert_level': 'normal'
            }
            
            result = self.service.get_real_time_insights()
            
            self.assertEqual(result['current_events_per_minute'], 5.5)
            self.assertEqual(result['active_threats'], 3)
            self.assertEqual(result['alert_level'], 'normal')
    
    def test_calculate_real_time_metrics(self):
        """Test calculating real-time metrics"""
        metrics = self.service._calculate_real_time_metrics()
        
        self.assertIn('current_events_per_minute', metrics)
        self.assertIn('active_threats', metrics)
        self.assertIn('system_load', metrics)
        self.assertIn('response_time_current', metrics)
        self.assertIn('anomaly_count', metrics)
        self.assertIn('alert_level', metrics)
    
    def test_get_historical_insights(self):
        """Test getting historical insights"""
        with patch.object(self.service, '_analyze_historical_data') as mock_analysis:
            mock_analysis.return_value = {
                'period_analysis': {
                    '90_days': {
                        'avg_security_score': 82.5,
                        'total_events': 45000,
                        'trend': 'improving'
                    },
                    '180_days': {
                        'avg_security_score': 78.0,
                        'total_events': 85000,
                        'trend': 'stable'
                    }
                },
                'year_over_year': {
                    'security_score_change': '+5.5%',
                    'event_volume_change': '+12.0%',
                    'threat_level_change': '-8.0%'
                },
                'seasonal_patterns': {
                    'peak_months': ['January', 'July', 'December'],
                    'low_months': ['April', 'September'],
                    'pattern_strength': 'moderate'
                }
            }
            
            result = self.service.get_historical_insights(days=180)
            
            self.assertEqual(result['period_analysis']['90_days']['avg_security_score'], 82.5)
            self.assertEqual(result['year_over_year']['security_score_change'], '+5.5%')
            self.assertIn('seasonal_patterns', result)
    
    def test_analyze_historical_data(self):
        """Test analyzing historical data"""
        analysis = self.service._analyze_historical_data(days=180)
        
        self.assertIn('period_analysis', analysis)
        self.assertIn('year_over_year', analysis)
        self.assertIn('seasonal_patterns', analysis)
    
    def test_get_predictive_insights(self):
        """Test getting predictive insights"""
        with patch.object(self.service, '_generate_predictive_models') as mock_models:
            mock_models.return_value = {
                'security_risk_prediction': {
                    'next_month_risk': 'medium',
                    'probability': 0.65,
                    'confidence': 0.85,
                    'key_factors': ['seasonal_increase', 'new_threat_types']
                },
                'resource_needs': {
                    'expected_load_increase': 0.25,
                    'recommended_staffing': 'increase_by_20%',
                    'infrastructure_needs': 'moderate_scaling'
                },
                'threat_evolution': {
                    'emerging_threats': ['ai-powered_attacks', 'supply_chain_attacks'],
                    'declining_threats': ['traditional_malware'],
                    'confidence_level': 0.75
                }
            }
            
            result = self.service.get_predictive_insights(days=30)
            
            self.assertEqual(result['security_risk_prediction']['next_month_risk'], 'medium')
            self.assertEqual(result['security_risk_prediction']['probability'], 0.65)
            self.assertIn('resource_needs', result)
            self.assertIn('threat_evolution', result)
    
    def test_generate_predictive_models(self):
        """Test generating predictive models"""
        models = self.service._generate_predictive_models(days=30)
        
        self.assertIn('security_risk_prediction', models)
        self.assertIn('resource_needs', models)
        self.assertIn('threat_evolution', models)
    
    def test_get_benchmark_insights(self):
        """Test getting benchmark insights"""
        with patch.object(self.service, '_benchmark_performance') as mock_benchmark:
            mock_benchmark.return_value = {
                'industry_comparison': {
                    'security_score': {
                        'your_score': 85.5,
                        'industry_average': 72.0,
                        'top_quartile': 85.0,
                        'percentile': 75
                    },
                    'threat_detection': {
                        'your_rate': 92.0,
                        'industry_average': 78.0,
                        'top_quartile': 90.0,
                        'percentile': 80
                    }
                },
                'competitive_position': {
                    'overall_ranking': 'above_average',
                    'strengths': ['threat_detection', 'incident_response'],
                    'improvement_areas': ['user_training', 'automation']
                },
                'recommendations': [
                    'Maintain current threat detection capabilities',
                    'Focus on user education programs'
                ]
            }
            
            result = self.service.get_benchmark_insights()
            
            self.assertEqual(result['industry_comparison']['security_score']['your_score'], 85.5)
            self.assertEqual(result['competitive_position']['overall_ranking'], 'above_average')
            self.assertIn('recommendations', result)
    
    def test_benchmark_performance(self):
        """Test benchmarking performance"""
        benchmark = self.service._benchmark_performance()
        
        self.assertIn('industry_comparison', benchmark)
        self.assertIn('competitive_position', benchmark)
        self.assertIn('recommendations', benchmark)
    
    def test_get_optimization_insights(self):
        """Test getting optimization insights"""
        with patch.object(self.service, '_identify_optimization_opportunities') as mock_optimization:
            mock_optimization.return_value = {
                'optimization_areas': [
                    {
                        'area': 'threat_detection',
                        'current_performance': 92.0,
                        'target_performance': 95.0,
                        'improvement_potential': 3.0,
                        'effort_required': 'medium',
                        'priority': 'high'
                    },
                    {
                        'area': 'incident_response',
                        'current_performance': 85.0,
                        'target_performance': 90.0,
                        'improvement_potential': 5.0,
                        'effort_required': 'low',
                        'priority': 'medium'
                    }
                ],
                'quick_wins': [
                    'Implement automated alert triage',
                    'Optimize log processing pipeline'
                ],
                'strategic_initiatives': [
                    'Deploy AI-powered threat detection',
                    'Enhance security automation'
                ]
            }
            
            result = self.service.get_optimization_insights()
            
            self.assertEqual(len(result['optimization_areas']), 2)
            self.assertEqual(result['optimization_areas'][0]['area'], 'threat_detection')
            self.assertIn('quick_wins', result)
            self.assertIn('strategic_initiatives', result)
    
    def test_identify_optimization_opportunities(self):
        """Test identifying optimization opportunities"""
        opportunities = self.service._identify_optimization_opportunities()
        
        self.assertIn('optimization_areas', opportunities)
        self.assertIn('quick_wins', opportunities)
        self.assertIn('strategic_initiatives', opportunities)
    
    def test_get_insight_dashboard(self):
        """Test getting insight dashboard"""
        with patch.object(self.service, '_build_dashboard') as mock_dashboard:
            mock_dashboard.return_value = {
                'overview': {
                    'security_score': 85.5,
                    'threat_level': 'medium',
                    'compliance_rate': 88.0,
                    'active_alerts': 3
                },
                'key_metrics': {
                    'events_today': 150,
                    'threats_detected': 8,
                    'incidents_open': 5,
                    'system_health': 'good'
                },
                'trends': [
                    {'metric': 'security_score', 'trend': 'improving', 'change': '+2.5%'},
                    {'metric': 'threat_detection', 'trend': 'stable', 'change': '0%'}
                ],
                'alerts': [
                    {
                        'type': 'threat_increase',
                        'message': '15% increase in sophisticated attacks',
                        'severity': 'warning'
                    }
                ]
            }
            
            result = self.service.get_insight_dashboard()
            
            self.assertEqual(result['overview']['security_score'], 85.5)
            self.assertEqual(result['key_metrics']['events_today'], 150)
            self.assertIn('trends', result)
            self.assertIn('alerts', result)
    
    def test_build_dashboard(self):
        """Test building dashboard"""
        dashboard = self.service._build_dashboard()
        
        self.assertIn('overview', dashboard)
        self.assertIn('key_metrics', dashboard)
        self.assertIn('trends', dashboard)
        self.assertIn('alerts', dashboard)
    
    def test_get_custom_insights(self):
        """Test getting custom insights"""
        custom_config = {
            'metrics': ['security_score', 'threat_detection_rate'],
            'filters': {'severity': ['high', 'critical']},
            'aggregations': ['daily', 'weekly'],
            'comparisons': ['period_over_period', 'year_over_year']
        }
        
        with patch.object(self.service, '_generate_custom_insights') as mock_custom:
            mock_custom.return_value = {
                'custom_metrics': {
                    'security_score': {
                        'current': 85.5,
                        'trend': 'improving',
                        'comparison': '+5.5%'
                    },
                    'threat_detection_rate': {
                        'current': 92.0,
                        'trend': 'stable',
                        'comparison': '0%'
                    }
                },
                'filtered_data': {
                    'high_severity_events': 25,
                    'critical_severity_events': 5
                },
                'aggregated_insights': {
                    'daily_average': 150.5,
                    'weekly_total': 1053.5
                }
            }
            
            result = self.service.get_custom_insights(custom_config)
            
            self.assertEqual(result['custom_metrics']['security_score']['current'], 85.5)
            self.assertEqual(result['filtered_data']['high_severity_events'], 25)
            self.assertIn('aggregated_insights', result)
    
    def test_generate_custom_insights(self):
        """Test generating custom insights"""
        custom_config = {
            'metrics': ['security_score'],
            'filters': {'severity': ['high']},
            'aggregations': ['daily']
        }
        
        insights = self.service._generate_custom_insights(custom_config)
        
        self.assertIn('custom_metrics', insights)
        self.assertIn('filtered_data', insights)
        self.assertIn('aggregated_insights', insights)
    
    def test_schedule_insight_generation(self):
        """Test scheduling insight generation"""
        with patch.object(self.service, '_create_scheduled_insight') as mock_create:
            mock_create.return_value = MagicMock()
            
            result = self.service.schedule_insight_generation(
                insight_type='daily',
                schedule='0 2 * * *',  # Daily at 2 AM
                parameters={'include_predictions': True}
            )
            
            self.assertTrue(result['success'])
            self.assertIn('schedule_id', result)
            mock_create.assert_called_once()
    
    def test_create_scheduled_insight(self):
        """Test creating scheduled insight"""
        with patch('api.security.models.ScheduledInsight.objects.create') as mock_create:
            mock_scheduled = MagicMock()
            mock_scheduled.id = 'scheduled-id'
            mock_create.return_value = mock_scheduled
            
            result = self.service._create_scheduled_insight(
                'daily',
                '0 2 * * *',
                {'include_predictions': True}
            )
            
            self.assertEqual(result, mock_scheduled)
            mock_create.assert_called_once()
    
    def test_get_scheduled_insights(self):
        """Test getting scheduled insights"""
        with patch('api.security.models.ScheduledInsight.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_scheduled_insights()
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['scheduled_insights']), 2)
    
    def test_execute_scheduled_insight(self):
        """Test executing scheduled insight"""
        with patch('api.security.models.ScheduledInsight.objects.get') as mock_get:
            mock_scheduled = MagicMock()
            mock_scheduled.insight_type = 'daily'
            mock_scheduled.parameters = {'include_predictions': True}
            mock_get.return_value = mock_scheduled
            
            with patch.object(self.service, 'create_daily_insight') as mock_create:
                mock_create.return_value = MagicMock()
                
                result = self.service.execute_scheduled_insight('scheduled-id')
                
                self.assertTrue(result['success'])
                self.assertIn('insight_id', result)
    
    def test_get_insight_subscriptions(self):
        """Test getting insight subscriptions"""
        with patch('api.security.models.InsightSubscription.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 10
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_insight_subscriptions(self.user.id)
            
            self.assertEqual(result['count'], 10)
            self.assertEqual(len(result['subscriptions']), 2)
    
    def test_create_insight_subscription(self):
        """Test creating insight subscription"""
        subscription_data = {
            'insight_type': 'daily_summary',
            'delivery_method': 'email',
            'schedule': 'daily',
            'filters': {'severity': ['high', 'critical']},
            'is_active': True
        }
        
        with patch('api.security.models.InsightSubscription.objects.create') as mock_create:
            mock_subscription = MagicMock()
            mock_subscription.id = 'subscription-id'
            mock_create.return_value = mock_subscription
            
            result = self.service.create_insight_subscription(
                self.user.id,
                subscription_data
            )
            
            self.assertEqual(result, mock_subscription)
            mock_create.assert_called_once()
    
    def test_deliver_insight_subscription(self):
        """Test delivering insight subscription"""
        subscription_data = {
            'user': self.user,
            'insight_type': 'daily_summary',
            'delivery_method': 'email',
            'email': self.user.email
        }
        
        with patch.object(self.service, '_generate_subscription_content') as mock_content:
            mock_content.return_value = {'subject': 'Daily Security Summary', 'body': 'Insight content...'}
            
            with patch.object(self.service, '_deliver_subscription') as mock_deliver:
                mock_deliver.return_value = True
                
                result = self.service.deliver_insight_subscription(subscription_data)
                
                self.assertTrue(result['success'])
                mock_content.assert_called_once()
                mock_deliver.assert_called_once()
    
    def test_generate_subscription_content(self):
        """Test generating subscription content"""
        subscription_data = {
            'insight_type': 'daily_summary',
            'filters': {'severity': ['high', 'critical']}
        }
        
        content = self.service._generate_subscription_content(subscription_data)
        
        self.assertIn('subject', content)
        self.assertIn('body', content)
    
    def test_deliver_subscription(self):
        """Test delivering subscription"""
        content = {
            'subject': 'Daily Security Summary',
            'body': 'Insight content...',
            'recipient': self.user.email
        }
        
        with patch('django.core.mail.send_mail') as mock_send:
            mock_send.return_value = True
            
            result = self.service._deliver_subscription(content)
            
            self.assertTrue(result)
            mock_send.assert_called_once()
    
    def test_get_insight_analytics(self):
        """Test getting insight analytics"""
        with patch.object(self.service, '_calculate_insight_analytics') as mock_analytics:
            mock_analytics.return_value = {
                'usage_metrics': {
                    'total_insights_generated': 1500,
                    'daily_average': 50,
                    'peak_usage_hour': 14,
                    'most_popular_type': 'daily_summary'
                },
                'performance_metrics': {
                    'avg_generation_time': 2.5,
                    'success_rate': 99.5,
                    'error_rate': 0.5
                },
                'user_engagement': {
                    'active_subscribers': 250,
                    'open_rate': 85.0,
                    'click_through_rate': 15.0
                },
                'trends': {
                    'usage_trend': 'increasing',
                    'engagement_trend': 'stable'
                }
            }
            
            result = self.service.get_insight_analytics(days=30)
            
            self.assertEqual(result['usage_metrics']['total_insights_generated'], 1500)
            self.assertEqual(result['performance_metrics']['success_rate'], 99.5)
            self.assertIn('user_engagement', result)
    
    def test_calculate_insight_analytics(self):
        """Test calculating insight analytics"""
        analytics = self.service._calculate_insight_analytics(days=30)
        
        self.assertIn('usage_metrics', analytics)
        self.assertIn('performance_metrics', analytics)
        self.assertIn('user_engagement', analytics)
        self.assertIn('trends', analytics)
    
    def test_get_insight_health_check(self):
        """Test getting insight health check"""
        with patch.object(self.service, '_perform_health_check') as mock_health:
            mock_health.return_value = {
                'overall_health': 'good',
                'component_status': {
                    'data_collection': 'healthy',
                    'processing_engine': 'healthy',
                    'storage_system': 'healthy',
                    'notification_system': 'healthy'
                },
                'performance_metrics': {
                    'avg_processing_time': 2.5,
                    'success_rate': 99.5,
                    'error_rate': 0.5
                },
                'alerts': [],
                'recommendations': [
                    'System performing optimally',
                    'Consider scaling for increased load'
                ]
            }
            
            result = self.service.get_insight_health_check()
            
            self.assertEqual(result['overall_health'], 'good')
            self.assertEqual(result['component_status']['data_collection'], 'healthy')
            self.assertIn('performance_metrics', result)
    
    def test_perform_health_check(self):
        """Test performing health check"""
        health = self.service._perform_health_check()
        
        self.assertIn('overall_health', health)
        self.assertIn('component_status', health)
        self.assertIn('performance_metrics', health)
        self.assertIn('alerts', health)
    
    def test_archive_old_insights(self):
        """Test archiving old insights"""
        with patch('api.security.models.SecurityInsight.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 100
            mock_queryset.delete.return_value = (100, {'api.security.SecurityInsight': 100})
            mock_filter.return_value = mock_queryset
            
            result = self.service.archive_old_insights(days=365)
            
            self.assertEqual(result['archived_count'], 100)
            mock_filter.assert_called_once()
    
    def test_get_archived_insights(self):
        """Test getting archived insights"""
        with patch('api.security.models.ArchivedInsight.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 50
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_archived_insights(
                date_from=timezone.now() - timedelta(days=30)
            )
            
            self.assertEqual(result['count'], 50)
            self.assertEqual(len(result['insights']), 2)
    
    def test_restore_archived_insight(self):
        """Test restoring archived insight"""
        with patch('api.security.models.ArchivedInsight.objects.get') as mock_get:
            mock_archived = MagicMock()
            mock_archived.insight_data = {
                'insight_date': '2023-01-01',
                'total_security_events': 100
            }
            mock_get.return_value = mock_archived
            
            with patch('api.security.models.SecurityInsight.objects.create') as mock_create:
                mock_insight = MagicMock()
                mock_insight.id = 'restored-id'
                mock_create.return_value = mock_insight
                
                result = self.service.restore_archived_insight('archive-id')
                
                self.assertEqual(result, mock_insight)
                mock_create.assert_called_once()
    
    def test_delete_archived_insight(self):
        """Test deleting archived insight"""
        with patch('api.security.models.ArchivedInsight.objects.get') as mock_get:
            mock_archived = MagicMock()
            mock_get.return_value = mock_archived
            
            with patch.object(mock_archived, 'delete') as mock_delete:
                result = self.service.delete_archived_insight('archive-id')
                
                self.assertTrue(result)
                mock_delete.assert_called_once()
    
    def test_get_insight_configuration(self):
        """Test getting insight configuration"""
        with patch('django.conf.settings.SECURITY_INSIGHT_CONFIG') as mock_config:
            mock_config.return_value = {
                'cache_timeout': 3600,
                'max_insights_per_day': 1000,
                'retention_days': 365,
                'enable_predictions': True,
                'notification_settings': {
                    'email_enabled': True,
                    'webhook_enabled': False
                }
            }
            
            result = self.service.get_insight_configuration()
            
            self.assertEqual(result['cache_timeout'], 3600)
            self.assertEqual(result['max_insights_per_day'], 1000)
            self.assertTrue(result['enable_predictions'])
    
    def test_update_insight_configuration(self):
        """Test updating insight configuration"""
        new_config = {
            'cache_timeout': 7200,
            'max_insights_per_day': 1500,
            'enable_predictions': False
        }
        
        with patch('django.conf.settings.SECURITY_INSIGHT_CONFIG') as mock_config:
            mock_config.return_value = new_config
            
            result = self.service.update_insight_configuration(new_config)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['updated_config']['cache_timeout'], 7200)
    
    def test_get_insight_permissions(self):
        """Test getting insight permissions"""
        with patch('api.security.models.InsightPermission.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_insight_permissions(self.user.id)
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['permissions']), 2)
    
    def test_grant_insight_permission(self):
        """Test granting insight permission"""
        permission_data = {
            'insight_type': 'executive_summary',
            'access_level': 'read',
            'granted_by': self.staff_user.id,
            'expires_at': timezone.now() + timedelta(days=30)
        }
        
        with patch('api.security.models.InsightPermission.objects.create') as mock_create:
            mock_permission = MagicMock()
            mock_permission.id = 'permission-id'
            mock_create.return_value = mock_permission
            
            result = self.service.grant_insight_permission(
                self.user.id,
                permission_data
            )
            
            self.assertEqual(result, mock_permission)
            mock_create.assert_called_once()
    
    def test_revoke_insight_permission(self):
        """Test revoking insight permission"""
        with patch('api.security.models.InsightPermission.objects.get') as mock_get:
            mock_permission = MagicMock()
            mock_get.return_value = mock_permission
            
            with patch.object(mock_permission, 'delete') as mock_delete:
                result = self.service.revoke_insight_permission('permission-id')
                
                self.assertTrue(result)
                mock_delete.assert_called_once()
    
    def test_check_insight_permission(self):
        """Test checking insight permission"""
        with patch('api.security.models.InsightPermission.objects.filter') as mock_filter:
            mock_permission = MagicMock()
            mock_permission.insight_type = 'executive_summary'
            mock_permission.access_level = 'read'
            mock_permission.is_active = True
            mock_queryset = MagicMock()
            mock_queryset.first.return_value = mock_permission
            mock_filter.return_value = mock_queryset
            
            result = self.service.check_insight_permission(
                self.user.id,
                'executive_summary',
                'read'
            )
            
            self.assertTrue(result['has_permission'])
            self.assertEqual(result['permission'], mock_permission)
    
    def test_get_insight_audit_log(self):
        """Test getting insight audit log"""
        with patch('api.security.models.InsightAuditLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 25
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_insight_audit_log(
                insight_type='daily_summary',
                days=30
            )
            
            self.assertEqual(result['count'], 25)
            self.assertEqual(len(result['audit_entries']), 2)
    
    def test_create_insight_audit_log(self):
        """Test creating insight audit log entry"""
        with patch('api.security.models.InsightAuditLog.objects.create') as mock_create:
            mock_log = MagicMock()
            mock_log.id = 'audit-log-id'
            mock_create.return_value = mock_log
            
            result = self.service.create_insight_audit_log(
                insight_type='daily_summary',
                action='generated',
                details={'processing_time': 2.5, 'events_processed': 150},
                user=self.staff_user
            )
            
            self.assertEqual(result, mock_log)
            mock_create.assert_called_once()