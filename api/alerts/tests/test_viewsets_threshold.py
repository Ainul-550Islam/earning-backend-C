"""
Tests for Threshold ViewSets
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog
from alerts.models.threshold import (
    ThresholdConfig, ThresholdBreach, AdaptiveThreshold, ThresholdHistory, ThresholdProfile
)
from alerts.viewsets.threshold import (
    ThresholdConfigViewSet, ThresholdBreachViewSet, AdaptiveThresholdViewSet,
    ThresholdHistoryViewSet, ThresholdProfileViewSet
)

User = get_user_model()


class ThresholdConfigViewSetTest(APITestCase):
    """Test cases for ThresholdConfigViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
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
            time_window_minutes=10,
            correlation_threshold=0.8,
            minimum_occurrences=3
        )
    
    def test_list_threshold_configs(self):
        """Test listing threshold configs"""
        url = '/api/alerts/thresholds/configs/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['threshold_type'], 'absolute')
    
    def test_create_threshold_config(self):
        """Test creating threshold config"""
        url = '/api/alerts/thresholds/configs/'
        data = {
            'alert_rule': self.alert_rule.id,
            'threshold_type': 'adaptive',
            'operator': 'greater_than',
            'primary_threshold': 80.0,
            'secondary_threshold': 95.0,
            'time_window_minutes': 15,
            'correlation_threshold': 0.9
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ThresholdConfig.objects.count(), 2)
    
    def test_retrieve_threshold_config(self):
        """Test retrieving single threshold config"""
        url = f'/api/alerts/thresholds/configs/{self.threshold_config.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['threshold_type'], 'absolute')
    
    def test_update_threshold_config(self):
        """Test updating threshold config"""
        url = f'/api/alerts/thresholds/configs/{self.threshold_config.id}/'
        data = {
            'primary_threshold': 90.0,
            'secondary_threshold': 95.0
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.threshold_config.refresh_from_db()
        self.assertEqual(self.threshold_config.primary_threshold, 90.0)
        self.assertEqual(self.threshold_config.secondary_threshold, 95.0)
    
    def test_delete_threshold_config(self):
        """Test deleting threshold config"""
        url = f'/api/alerts/thresholds/configs/{self.threshold_config.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ThresholdConfig.objects.count(), 0)
    
    def test_evaluate_threshold_condition(self):
        """Test evaluating threshold condition"""
        url = f'/api/alerts/thresholds/configs/{self.threshold_config.id}/evaluate/'
        data = {
            'value': 95.0
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('result', response.data)
        self.assertIn('breached', response.data)
    
    def test_get_threshold_effectiveness(self):
        """Test getting threshold effectiveness"""
        url = f'/api/alerts/thresholds/configs/{self.threshold_config.id}/effectiveness/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('effectiveness_score', response.data)
        self.assertIn('breach_count', response.data)
    
    def test_optimize_threshold(self):
        """Test optimizing threshold"""
        url = f'/api/alerts/thresholds/configs/{self.threshold_config.id}/optimize/'
        data = {
            'optimization_method': 'statistical',
            'target_false_positive_rate': 0.05
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('optimized_threshold', response.data)
        self.assertIn('improvement_score', response.data)


class ThresholdBreachViewSetTest(APITestCase):
    """Test cases for ThresholdBreachViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.threshold_config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='absolute',
            operator='greater_than',
            primary_threshold=85.0
        )
        
        self.threshold_breach = ThresholdBreach.objects.create(
            threshold_config=self.threshold_config,
            severity='high',
            breach_value=95.0,
            threshold_value=85.0,
            breach_percentage=11.76
        )
    
    def test_list_threshold_breaches(self):
        """Test listing threshold breaches"""
        url = '/api/alerts/thresholds/breaches/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['severity'], 'high')
    
    def test_create_threshold_breach(self):
        """Test creating threshold breach"""
        url = '/api/alerts/thresholds/breaches/'
        data = {
            'threshold_config': self.threshold_config.id,
            'severity': 'critical',
            'breach_value': 100.0,
            'threshold_value': 85.0,
            'breach_percentage': 17.65
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ThresholdBreach.objects.count(), 2)
    
    def test_retrieve_threshold_breach(self):
        """Test retrieving single threshold breach"""
        url = f'/api/alerts/thresholds/breaches/{self.threshold_breach.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['breach_value'], 95.0)
    
    def test_resolve_threshold_breach(self):
        """Test resolving threshold breach"""
        url = f'/api/alerts/thresholds/breaches/{self.threshold_breach.id}/resolve/'
        data = {
            'resolution_note': 'Fixed the threshold breach'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.threshold_breach.refresh_from_db()
        self.assertTrue(self.threshold_breach.is_resolved)
        self.assertEqual(self.threshold_breach.resolution_note, 'Fixed the threshold breach')
    
    def test_get_breaches_by_severity(self):
        """Test getting breaches by severity"""
        url = '/api/alerts/thresholds/breaches/by_severity/high/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_active_breaches(self):
        """Test getting active breaches"""
        url = '/api/alerts/thresholds/breaches/active/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_breach_statistics(self):
        """Test getting breach statistics"""
        url = '/api/alerts/thresholds/breaches/statistics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_breaches', response.data)
        self.assertIn('active_breaches', response.data)
        self.assertIn('resolved_breaches', response.data)
    
    def test_get_breach_trends(self):
        """Test getting breach trends"""
        url = '/api/alerts/thresholds/breaches/trends/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('daily_trends', response.data)
        self.assertIn('severity_trends', response.data)


class AdaptiveThresholdViewSetTest(APITestCase):
    """Test cases for AdaptiveThresholdViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.threshold_config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='absolute',
            operator='greater_than',
            primary_threshold=85.0
        )
        
        self.adaptive_threshold = AdaptiveThreshold.objects.create(
            threshold_config=self.threshold_config,
            adaptation_method='statistical',
            learning_period_days=30,
            confidence_threshold=0.9,
            sensitivity=0.8,
            window_size_minutes=60,
            baseline_days=7
        )
    
    def test_list_adaptive_thresholds(self):
        """Test listing adaptive thresholds"""
        url = '/api/alerts/thresholds/adaptive/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['adaptation_method'], 'statistical')
    
    def test_create_adaptive_threshold(self):
        """Test creating adaptive threshold"""
        url = '/api/alerts/thresholds/adaptive/'
        data = {
            'threshold_config': self.threshold_config.id,
            'adaptation_method': 'machine_learning',
            'learning_period_days': 60,
            'confidence_threshold': 0.95,
            'sensitivity': 0.7
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AdaptiveThreshold.objects.count(), 2)
    
    def test_retrieve_adaptive_threshold(self):
        """Test retrieving single adaptive threshold"""
        url = f'/api/alerts/thresholds/adaptive/{self.adaptive_threshold.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['adaptation_method'], 'statistical')
    
    def test_train_adaptive_threshold(self):
        """Test training adaptive threshold"""
        url = f'/api/alerts/thresholds/adaptive/{self.adaptive_threshold.id}/train/'
        data = {
            'training_data_days': 30,
            'validation_split': 0.2
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('training_result', response.data)
        self.assertIn('model_accuracy', response.data)
    
    def test_adapt_threshold(self):
        """Test adapting threshold"""
        url = f'/api/alerts/thresholds/adaptive/{self.adaptive_threshold.id}/adapt/'
        data = {
            'new_threshold': 90.0,
            'reason': 'Increased due to high variability'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('adaptation_result', response.data)
    
    def test_get_adaptation_history(self):
        """Test getting adaptation history"""
        url = f'/api/alerts/thresholds/adaptive/{self.adaptive_threshold.id}/history/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('adaptations', response.data)
    
    def test_get_training_status(self):
        """Test getting training status"""
        url = f'/api/alerts/thresholds/adaptive/{self.adaptive_threshold.id}/training_status/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('progress', response.data)
    
    def test_reset_adaptive_threshold(self):
        """Test resetting adaptive threshold"""
        url = f'/api/alerts/thresholds/adaptive/{self.adaptive_threshold.id}/reset/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reset_result', response.data)


class ThresholdHistoryViewSetTest(APITestCase):
    """Test cases for ThresholdHistoryViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.threshold_config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='absolute',
            operator='greater_than',
            primary_threshold=85.0
        )
        
        self.adaptive_threshold = AdaptiveThreshold.objects.create(
            threshold_config=self.threshold_config,
            adaptation_method='statistical',
            learning_period_days=30
        )
        
        self.threshold_history = ThresholdHistory.objects.create(
            adaptive_threshold=self.adaptive_threshold,
            change_type='adaptation',
            old_threshold=85.0,
            new_threshold=90.0,
            change_percentage=5.88,
            reason='Increased due to high variability'
        )
    
    def test_list_threshold_history(self):
        """Test listing threshold history"""
        url = '/api/alerts/thresholds/history/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['change_type'], 'adaptation')
    
    def test_create_threshold_history(self):
        """Test creating threshold history"""
        url = '/api/alerts/thresholds/history/'
        data = {
            'adaptive_threshold': self.adaptive_threshold.id,
            'change_type': 'manual',
            'old_threshold': 90.0,
            'new_threshold': 95.0,
            'change_percentage': 5.56,
            'reason': 'Manual adjustment by operator'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ThresholdHistory.objects.count(), 2)
    
    def test_retrieve_threshold_history(self):
        """Test retrieving single threshold history"""
        url = f'/api/alerts/thresholds/history/{self.threshold_history.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['change_type'], 'adaptation')
    
    def test_get_history_by_change_type(self):
        """Test getting history by change type"""
        url = '/api/alerts/thresholds/history/by_type/adaptation/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_history_by_adaptive_threshold(self):
        """Test getting history by adaptive threshold"""
        url = f'/api/alerts/thresholds/history/by_adaptive/{self.adaptive_threshold.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_history_trends(self):
        """Test getting history trends"""
        url = '/api/alerts/thresholds/history/trends/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('trend_data', response.data)
        self.assertIn('change_frequency', response.data)
    
    def test_get_adaptation_frequency(self):
        """Test getting adaptation frequency"""
        url = f'/api/alerts/thresholds/history/frequency/{self.adaptive_threshold.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('frequency', response.data)
        self.assertIn('period', response.data)


class ThresholdProfileViewSetTest(APITestCase):
    """Test cases for ThresholdProfileViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.threshold_profile = ThresholdProfile.objects.create(
            name='Production Thresholds',
            description='Default thresholds for production environment',
            profile_type='environment',
            is_default=True,
            is_active=True,
            threshold_settings={
                'cpu_usage': {'warning': 70.0, 'critical': 90.0},
                'memory_usage': {'warning': 80.0, 'critical': 95.0},
                'disk_usage': {'warning': 85.0, 'critical': 95.0}
            },
            alert_type_mappings={
                'cpu_usage': 'high',
                'memory_usage': 'medium',
                'disk_usage': 'low'
            }
        )
    
    def test_list_threshold_profiles(self):
        """Test listing threshold profiles"""
        url = '/api/alerts/thresholds/profiles/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['profile_type'], 'environment')
    
    def test_create_threshold_profile(self):
        """Test creating threshold profile"""
        url = '/api/alerts/thresholds/profiles/'
        data = {
            'name': 'Development Thresholds',
            'description': 'Thresholds for development environment',
            'profile_type': 'environment',
            'is_default': False,
            'is_active': True,
            'threshold_settings': {
                'cpu_usage': {'warning': 80.0, 'critical': 95.0},
                'memory_usage': {'warning': 85.0, 'critical': 98.0}
            },
            'alert_type_mappings': {
                'cpu_usage': 'medium',
                'memory_usage': 'low'
            }
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ThresholdProfile.objects.count(), 2)
    
    def test_retrieve_threshold_profile(self):
        """Test retrieving single threshold profile"""
        url = f'/api/alerts/thresholds/profiles/{self.threshold_profile.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Production Thresholds')
    
    def test_apply_profile_to_rules(self):
        """Test applying profile to rules"""
        # Create some alert rules
        alert_rule1 = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='low',
            threshold_value=50.0
        )
        
        alert_rule2 = AlertRule.objects.create(
            name='Memory Alert',
            alert_type='memory_usage',
            severity='low',
            threshold_value=60.0
        )
        
        url = f'/api/alerts/thresholds/profiles/{self.threshold_profile.id}/apply/'
        data = {
            'rule_ids': [alert_rule1.id, alert_rule2.id]
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('applied_rules', response.data)
        self.assertIn('updated_count', response.data)
    
    def test_get_profile_thresholds(self):
        """Test getting profile thresholds"""
        url = f'/api/alerts/thresholds/profiles/{self.threshold_profile.id}/thresholds/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('cpu_usage', response.data)
        self.assertIn('memory_usage', response.data)
    
    def test_get_profile_mappings(self):
        """Test getting profile mappings"""
        url = f'/api/alerts/thresholds/profiles/{self.threshold_profile.id}/mappings/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('cpu_usage', response.data)
        self.assertIn('memory_usage', response.data)
    
    def test_validate_profile(self):
        """Test validating profile"""
        url = f'/api/alerts/thresholds/profiles/{self.threshold_profile.id}/validate/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_valid', response.data)
        self.assertIn('validation_errors', response.data)
    
    def test_clone_profile(self):
        """Test cloning profile"""
        url = f'/api/alerts/thresholds/profiles/{self.threshold_profile.id}/clone/'
        data = {
            'name': 'Cloned Profile',
            'description': 'Cloned from Production Thresholds'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('cloned_profile', response.data)
    
    def test_export_profile(self):
        """Test exporting profile"""
        url = f'/api/alerts/thresholds/profiles/{self.threshold_profile.id}/export/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('profile_data', response.data)
        self.assertIn('export_format', response.data)
    
    def test_import_profile(self):
        """Test importing profile"""
        url = '/api/alerts/thresholds/profiles/import/'
        data = {
            'name': 'Imported Profile',
            'profile_data': {
                'cpu_usage': {'warning': 75.0, 'critical': 92.0},
                'memory_usage': {'warning': 82.0, 'critical': 96.0}
            },
            'alert_type_mappings': {
                'cpu_usage': 'medium',
                'memory_usage': 'low'
            }
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('imported_profile', response.data)
