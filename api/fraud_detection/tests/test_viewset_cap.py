"""
Comprehensive CAP (Content Analysis Platform) viewset testing.

This test file covers all CAP-specific viewsets and functionality
that were previously untested in the fraud_detection module.
"""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.test import APIRequestFactory
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend

from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, FraudCase, FraudCaseEvidence
)
from api.fraud_detection.viewset_cap import (
    CAPFraudAnalysisViewSet, CAPPatternAnalysisViewSet, CAPUserBehaviorViewSet,
    CAPDeviceAnalysisViewSet, CAPNetworkAnalysisViewSet, CAPReportViewSet,
    CAPAlertViewSet, CAPDashboardViewSet
)
from api.fraud_detection.serializers_cap import (
    CAPFraudAnalysisSerializer, CAPPatternAnalysisSerializer, CAPUserBehaviorSerializer,
    CAPDeviceAnalysisSerializer, CAPNetworkAnalysisSerializer, CAPReportSerializer,
    CAPAlertSerializer, CAPDashboardSerializer
)
from api.users.models import User

User = get_user_model()


class CAPFraudAnalysisViewSetTest(APITestCase):
    """Test cases for CAPFraudAnalysisViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.factory = APIRequestFactory()
        cache.clear()
    
    def test_cap_fraud_analysis_list(self):
        """Test listing CAP fraud analyses"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-fraud-analysis-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_cap_fraud_analysis_create(self):
        """Test creating a CAP fraud analysis"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-fraud-analysis-list')
        data = {
            'user': self.user.pk,
            'analysis_type': 'behavioral',
            'context': {
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0 (Test Browser)',
                'session_id': 'test-session-123'
            },
            'parameters': {
                'time_window': '24h',
                'include_historical': True
            }
        }
        
        with patch('api.fraud_detection.services_cap.CAPAnalysisService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.analyze_fraud.return_value = {
                'risk_score': 75,
                'risk_level': 'medium',
                'detected_patterns': ['suspicious_login_times'],
                'confidence': 0.85,
                'recommendations': ['monitor_user', 'additional_verification']
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            result_data = response.data
            self.assertIn('risk_score', result_data)
            self.assertIn('risk_level', result_data)
            self.assertIn('detected_patterns', result_data)
            self.assertEqual(result_data['risk_score'], 75)
    
    def test_cap_fraud_analysis_bulk_create(self):
        """Test bulk creating CAP fraud analyses"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-fraud-analysis-bulk-create')
        
        # Create additional users for bulk analysis
        users = []
        for i in range(3):
            user = User.objects.create_user(
                username=f'bulkuser{i}',
                email=f'bulkuser{i}@example.com',
                password='bulkpass123'
            )
            users.append(user)
        
        data = {
            'analyses': [
                {
                    'user': users[0].pk,
                    'analysis_type': 'behavioral',
                    'context': {'ip_address': '192.168.1.1'},
                    'parameters': {'time_window': '24h'}
                },
                {
                    'user': users[1].pk,
                    'analysis_type': 'network',
                    'context': {'ip_address': '192.168.1.2'},
                    'parameters': {'include_network': True}
                },
                {
                    'user': users[2].pk,
                    'analysis_type': 'device',
                    'context': {'device_id': 'test-device'},
                    'parameters': {'device_analysis': True}
                }
            ]
        }
        
        with patch('api.fraud_detection.services_cap.CAPAnalysisService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.analyze_fraud.return_value = {
                'risk_score': 50,
                'risk_level': 'low',
                'detected_patterns': [],
                'confidence': 0.7,
                'recommendations': ['continue_monitoring']
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            result_data = response.data
            self.assertIn('results', result_data)
            self.assertEqual(len(result_data['results']), 3)
            self.assertIn('summary', result_data)
    
    def test_cap_fraud_analysis_retrieve(self):
        """Test retrieving a specific CAP fraud analysis"""
        # First create an analysis
        self.client.force_authenticate(user=self.admin_user)
        create_url = reverse('frauddetection:cap-fraud-analysis-list')
        
        with patch('api.fraud_detection.services_cap.CAPAnalysisService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.analyze_fraud.return_value = {
                'risk_score': 85,
                'risk_level': 'high',
                'detected_patterns': ['multiple_accounts'],
                'confidence': 0.95,
                'recommendations': ['immediate_review', 'account_suspension']
            }
            
            create_response = self.client.post(create_url, {
                'user': self.user.pk,
                'analysis_type': 'behavioral',
                'context': {'ip_address': '192.168.1.1'},
                'parameters': {'time_window': '24h'}
            }, format='json')
            
            analysis_id = create_response.data['id']
            
            # Retrieve the analysis
            retrieve_url = reverse('frauddetection:cap-fraud-analysis-detail', kwargs={'pk': analysis_id})
            response = self.client.get(retrieve_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['risk_score'], 85)
    
    def test_cap_fraud_analysis_filtering(self):
        """Test filtering CAP fraud analyses"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-fraud-analysis-list')
        
        # Test filtering by analysis_type
        response = self.client.get(url, {'analysis_type': 'behavioral'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test filtering by risk_level
        response = self.client.get(url, {'risk_level': 'high'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test filtering by date range
        response = self.client.get(url, {
            'created_after': timezone.now().date(),
            'created_before': timezone.now().date()
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cap_fraud_analysis_custom_actions(self):
        """Test custom actions for CAP fraud analysis"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create an analysis first
        with patch('api.fraud_detection.services_cap.CAPAnalysisService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.analyze_fraud.return_value = {
                'risk_score': 75,
                'risk_level': 'medium',
                'detected_patterns': ['suspicious_activity'],
                'confidence': 0.8,
                'recommendations': ['monitor']
            }
            
            create_url = reverse('frauddetection:cap-fraud-analysis-list')
            create_response = self.client.post(create_url, {
                'user': self.user.pk,
                'analysis_type': 'behavioral',
                'context': {'ip_address': '192.168.1.1'},
                'parameters': {'time_window': '24h'}
            }, format='json')
            
            analysis_id = create_response.data['id']
            
            # Test reanalyze action
            reanalyze_url = reverse('frauddetection:cap-fraud-analysis-reanalyze', kwargs={'pk': analysis_id})
            response = self.client.post(reanalyze_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Test export action
            export_url = reverse('frauddetection:cap-fraud-analysis-export', kwargs={'pk': analysis_id})
            response = self.client.post(export_url, {'format': 'json'})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('export_data', response.data)


class CAPPatternAnalysisViewSetTest(APITestCase):
    """Test cases for CAPPatternAnalysisViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        cache.clear()
    
    def test_cap_pattern_analysis_list(self):
        """Test listing CAP pattern analyses"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-pattern-analysis-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cap_pattern_analysis_create(self):
        """Test creating a CAP pattern analysis"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-pattern-analysis-list')
        data = {
            'pattern_type': 'behavioral',
            'analysis_parameters': {
                'time_window': '7d',
                'user_segment': 'high_risk',
                'pattern_types': ['login_frequency', 'device_switching']
            },
            'scope': {
                'user_ids': [1, 2, 3],
                'date_range': {
                    'start': '2023-01-01',
                    'end': '2023-01-07'
                }
            }
        }
        
        with patch('api.fraud_detection.services_cap.CAPPatternService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.analyze_patterns.return_value = {
                'detected_patterns': [
                    {
                        'pattern_id': 'login_anomaly_001',
                        'pattern_type': 'temporal',
                        'confidence': 0.92,
                        'affected_users': 15,
                        'description': 'Unusual login times detected'
                    }
                ],
                'summary': {
                    'total_patterns': 1,
                    'high_confidence_patterns': 1,
                    'affected_users': 15
                }
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            result_data = response.data
            self.assertIn('detected_patterns', result_data)
            self.assertIn('summary', result_data)
            self.assertEqual(len(result_data['detected_patterns']), 1)
    
    def test_cap_pattern_analysis_historical(self):
        """Test historical pattern analysis"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-pattern-analysis-historical')
        data = {
            'pattern_id': 'login_anomaly_001',
            'historical_parameters': {
                'time_range': '30d',
                'comparison_period': 'previous_period'
            }
        }
        
        with patch('api.fraud_detection.services_cap.CAPPatternService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.analyze_historical_patterns.return_value = {
                'trend_data': {
                    'frequency_trend': 'increasing',
                    'confidence_trend': 'stable',
                    'severity_trend': 'increasing'
                },
                'comparisons': {
                    'current_period': 25,
                    'previous_period': 18,
                    'change_percentage': 38.9
                }
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            result_data = response.data
            self.assertIn('trend_data', result_data)
            self.assertIn('comparisons', result_data)


class CAPUserBehaviorViewSetTest(APITestCase):
    """Test cases for CAPUserBehaviorViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        cache.clear()
    
    def test_cap_user_behavior_list(self):
        """Test listing CAP user behavior analyses"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-user-behavior-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cap_user_behavior_create(self):
        """Test creating a CAP user behavior analysis"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-user-behavior-list')
        data = {
            'user': self.user.pk,
            'behavior_type': 'login_pattern',
            'analysis_window': '30d',
            'parameters': {
                'include_device_analysis': True,
                'include_location_analysis': True,
                'include_time_analysis': True
            }
        }
        
        with patch('api.fraud_detection.services_cap.CAPBehaviorService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.analyze_user_behavior.return_value = {
                'behavior_score': 65,
                'anomalies': [
                    {
                        'type': 'time_anomaly',
                        'description': 'Unusual login times',
                        'severity': 'medium',
                        'confidence': 0.78
                    }
                ],
                'patterns': {
                    'login_frequency': 'normal',
                    'device_usage': 'stable',
                    'location_consistency': 'variable'
                },
                'recommendations': ['monitor_time_patterns', 'verify_locations']
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            result_data = response.data
            self.assertIn('behavior_score', result_data)
            self.assertIn('anomalies', result_data)
            self.assertIn('patterns', result_data)
            self.assertEqual(result_data['behavior_score'], 65)
    
    def test_cap_user_behavior_timeline(self):
        """Test user behavior timeline analysis"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-user-behavior-timeline')
        data = {
            'user': self.user.pk,
            'timeline_parameters': {
                'start_date': '2023-01-01',
                'end_date': '2023-01-31',
                'granularity': 'daily'
            }
        }
        
        with patch('api.fraud_detection.services_cap.CAPBehaviorService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.generate_behavior_timeline.return_value = {
                'timeline_data': [
                    {
                        'date': '2023-01-01',
                        'behavior_score': 45,
                        'events': ['login', 'logout'],
                        'anomalies': []
                    },
                    {
                        'date': '2023-01-15',
                        'behavior_score': 78,
                        'events': ['login', 'suspicious_activity'],
                        'anomalies': ['time_anomaly']
                    }
                ],
                'summary': {
                    'average_score': 61.5,
                    'peak_score': 78,
                    'total_anomalies': 1
                }
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            result_data = response.data
            self.assertIn('timeline_data', result_data)
            self.assertIn('summary', result_data)


class CAPDeviceAnalysisViewSetTest(APITestCase):
    """Test cases for CAPDeviceAnalysisViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        cache.clear()
    
    def test_cap_device_analysis_list(self):
        """Test listing CAP device analyses"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-device-analysis-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cap_device_analysis_create(self):
        """Test creating a CAP device analysis"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-device-analysis-list')
        data = {
            'device_id': 'test-device-123',
            'device_fingerprint': 'abc123def456',
            'analysis_type': 'comprehensive',
            'parameters': {
                'include_historical': True,
                'include_cross_user': True,
                'time_window': '90d'
            }
        }
        
        with patch('api.fraud_detection.services_cap.CAPDeviceService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.analyze_device.return_value = {
                'device_risk_score': 72,
                'trust_level': 'medium',
                'associated_users': 3,
                'risk_factors': [
                    {
                        'factor': 'multiple_accounts',
                        'severity': 'high',
                        'description': 'Device used by multiple accounts'
                    }
                ],
                'recommendations': ['require_additional_verification']
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            result_data = response.data
            self.assertIn('device_risk_score', result_data)
            self.assertIn('trust_level', result_data)
            self.assertIn('associated_users', result_data)
            self.assertEqual(result_data['device_risk_score'], 72)
    
    def test_cap_device_analysis_cross_reference(self):
        """Test device cross-reference analysis"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-device-analysis-cross-reference')
        data = {
            'device_fingerprints': ['abc123', 'def456', 'ghi789'],
            'analysis_parameters': {
                'include_user_correlation': True,
                'include_temporal_analysis': True
            }
        }
        
        with patch('api.fraud_detection.services_cap.CAPDeviceService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.cross_reference_devices.return_value = {
                'correlations': [
                    {
                        'device_1': 'abc123',
                        'device_2': 'def456',
                        'correlation_strength': 0.85,
                        'shared_users': 2,
                        'correlation_type': 'user_overlap'
                    }
                ],
                'summary': {
                    'total_devices': 3,
                    'correlated_pairs': 1,
                    'high_correlations': 1
                }
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            result_data = response.data
            self.assertIn('correlations', result_data)
            self.assertIn('summary', result_data)


class CAPNetworkAnalysisViewSetTest(APITestCase):
    """Test cases for CAPNetworkAnalysisViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        cache.clear()
    
    def test_cap_network_analysis_list(self):
        """Test listing CAP network analyses"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-network-analysis-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cap_network_analysis_create(self):
        """Test creating a CAP network analysis"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-network-analysis-list')
        data = {
            'network_type': 'ip_network',
            'target': '192.168.1.0/24',
            'analysis_parameters': {
                'time_window': '7d',
                'include_reputation': True,
                'include_geolocation': True
            }
        }
        
        with patch('api.fraud_detection.services_cap.CAPNetworkService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.analyze_network.return_value = {
                'network_risk_score': 68,
                'suspicious_ips': ['192.168.1.100', '192.168.1.101'],
                'risk_distribution': {
                    'high_risk': 2,
                    'medium_risk': 5,
                    'low_risk': 247
                },
                'recommendations': ['block_suspicious_ips', 'monitor_network']
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            result_data = response.data
            self.assertIn('network_risk_score', result_data)
            self.assertIn('suspicious_ips', result_data)
            self.assertIn('risk_distribution', result_data)
            self.assertEqual(result_data['network_risk_score'], 68)
    
    def test_cap_network_analysis_topology(self):
        """Test network topology analysis"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-network-analysis-topology')
        data = {
            'analysis_scope': 'user_connections',
            'parameters': {
                'max_depth': 3,
                'include_temporal': True,
                'time_window': '30d'
            }
        }
        
        with patch('api.fraud_detection.services_cap.CAPNetworkService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.analyze_network_topology.return_value = {
                'nodes': [
                    {
                        'id': 'user_1',
                        'type': 'user',
                        'risk_score': 45,
                        'connections': 3
                    },
                    {
                        'id': 'ip_192.168.1.1',
                        'type': 'ip',
                        'risk_score': 72,
                        'connections': 5
                    }
                ],
                'edges': [
                    {
                        'source': 'user_1',
                        'target': 'ip_192.168.1.1',
                        'weight': 0.8,
                        'connection_type': 'login'
                    }
                ],
                'metrics': {
                    'total_nodes': 2,
                    'total_edges': 1,
                    'clustering_coefficient': 0.0
                }
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            result_data = response.data
            self.assertIn('nodes', result_data)
            self.assertIn('edges', result_data)
            self.assertIn('metrics', result_data)


class CAPReportViewSetTest(APITestCase):
    """Test cases for CAPReportViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        cache.clear()
    
    def test_cap_report_list(self):
        """Test listing CAP reports"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-report-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cap_report_create(self):
        """Test creating a CAP report"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-report-list')
        data = {
            'report_type': 'comprehensive',
            'title': 'Monthly Fraud Analysis Report',
            'parameters': {
                'time_range': '30d',
                'include_sections': ['summary', 'trends', 'recommendations'],
                'format': 'detailed'
            }
        }
        
        with patch('api.fraud_detection.services_cap.CAPReportService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.generate_report.return_value = {
                'report_id': 'report_123',
                'title': 'Monthly Fraud Analysis Report',
                'generated_at': timezone.now().isoformat(),
                'sections': {
                    'summary': {
                        'total_analyses': 150,
                        'high_risk_cases': 12,
                        'blocked_attempts': 8
                    },
                    'trends': {
                        'fraud_trend': 'increasing',
                        'risk_areas': ['account_takeover', 'synthetic_identity']
                    },
                    'recommendations': [
                        'Enhance authentication',
                        'Implement behavioral analysis'
                    ]
                }
            }
            
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            result_data = response.data
            self.assertIn('report_id', result_data)
            self.assertIn('sections', result_data)
            self.assertEqual(result_data['title'], 'Monthly Fraud Analysis Report')
    
    def test_cap_report_export(self):
        """Test exporting CAP reports"""
        self.client.force_authenticate(user=self.admin_user)
        
        # First create a report
        with patch('api.fraud_detection.services_cap.CAPReportService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.generate_report.return_value = {
                'report_id': 'report_123',
                'title': 'Test Report',
                'sections': {'summary': {'total': 100}}
            }
            
            create_url = reverse('frauddetection:cap-report-list')
            create_response = self.client.post(create_url, {
                'report_type': 'summary',
                'title': 'Test Report',
                'parameters': {'time_range': '7d'}
            }, format='json')
            
            report_id = create_response.data['report_id']
            
            # Export the report
            export_url = reverse('frauddetection:cap-report-export', kwargs={'pk': report_id})
            export_data = {
                'format': 'pdf',
                'include_sections': ['summary', 'trends']
            }
            
            response = self.client.post(export_url, export_data, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            result_data = response.data
            self.assertIn('export_url', result_data)
            self.assertIn('format', result_data)


class CAPAlertViewSetTest(APITestCase):
    """Test cases for CAPAlertViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        cache.clear()
    
    def test_cap_alert_list(self):
        """Test listing CAP alerts"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-alert-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cap_alert_create(self):
        """Test creating a CAP alert"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-alert-list')
        data = {
            'alert_type': 'pattern_detected',
            'severity': 'high',
            'title': 'Suspicious Pattern Detected',
            'description': 'Unusual user behavior pattern detected',
            'source': 'cap_analysis',
            'data': {
                'pattern_id': 'behavior_anomaly_001',
                'confidence': 0.92,
                'affected_users': [1, 2, 3]
            }
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        result_data = response.data
        self.assertIn('alert_id', result_data)
        self.assertEqual(result_data['severity'], 'high')
    
    def test_cap_alert_bulk_create(self):
        """Test bulk creating CAP alerts"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-alert-bulk-create')
        data = {
            'alerts': [
                {
                    'alert_type': 'threshold_exceeded',
                    'severity': 'medium',
                    'title': 'Risk Threshold Exceeded',
                    'description': 'User risk score exceeded threshold',
                    'source': 'cap_analysis',
                    'data': {'user_id': 1, 'risk_score': 85}
                },
                {
                    'alert_type': 'network_anomaly',
                    'severity': 'high',
                    'title': 'Network Anomaly Detected',
                    'description': 'Suspicious network activity detected',
                    'source': 'cap_analysis',
                    'data': {'ip_address': '192.168.1.100', 'anomaly_type': 'unusual_traffic'}
                }
            ]
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        result_data = response.data
        self.assertIn('results', result_data)
        self.assertEqual(len(result_data['results']), 2)
        self.assertIn('summary', result_data)


class CAPDashboardViewSetTest(APITestCase):
    """Test cases for CAPDashboardViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        cache.clear()
    
    def test_cap_dashboard_overview(self):
        """Test CAP dashboard overview"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-dashboard-overview')
        
        with patch('api.fraud_detection.services_cap.CAPDashboardService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.get_overview.return_value = {
                'summary': {
                    'total_analyses': 1250,
                    'active_alerts': 15,
                    'high_risk_users': 8,
                    'blocked_attempts': 23
                },
                'trends': {
                    'daily_analyses': [45, 52, 48, 61, 55],
                    'risk_distribution': {'low': 60, 'medium': 30, 'high': 10}
                },
                'top_alerts': [
                    {
                        'type': 'pattern_detected',
                        'count': 8,
                        'severity': 'high'
                    }
                ]
            }
            
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            result_data = response.data
            self.assertIn('summary', result_data)
            self.assertIn('trends', result_data)
            self.assertIn('top_alerts', result_data)
            self.assertEqual(result_data['summary']['total_analyses'], 1250)
    
    def test_cap_dashboard_metrics(self):
        """Test CAP dashboard metrics"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-dashboard-metrics')
        
        with patch('api.fraud_detection.services_cap.CAPDashboardService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.get_metrics.return_value = {
                'performance_metrics': {
                    'analysis_time_avg': 2.3,
                    'accuracy_rate': 0.94,
                    'false_positive_rate': 0.06
                },
                'volume_metrics': {
                    'analyses_per_day': 125,
                    'alerts_per_day': 8,
                    'peak_hours': ['09:00', '14:00', '18:00']
                },
                'efficiency_metrics': {
                    'auto_resolution_rate': 0.75,
                    'manual_review_required': 0.25
                }
            }
            
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            result_data = response.data
            self.assertIn('performance_metrics', result_data)
            self.assertIn('volume_metrics', result_data)
            self.assertIn('efficiency_metrics', result_data)
    
    def test_cap_dashboard_real_time(self):
        """Test CAP dashboard real-time data"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:cap-dashboard-real-time')
        
        with patch('api.fraud_detection.services_cap.CAPDashboardService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.get_real_time_data.return_value = {
                'current_analyses': 3,
                'active_alerts': 7,
                'system_status': 'healthy',
                'recent_activities': [
                    {
                        'type': 'analysis_completed',
                        'timestamp': timezone.now().isoformat(),
                        'details': 'User behavior analysis completed'
                    }
                ]
            }
            
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            result_data = response.data
            self.assertIn('current_analyses', result_data)
            self.assertIn('active_alerts', result_data)
            self.assertIn('system_status', result_data)
            self.assertEqual(result_data['current_analyses'], 3)
