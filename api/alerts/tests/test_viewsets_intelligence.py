"""
Tests for Intelligence ViewSets
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog
from alerts.models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel, AlertNoise, RootCauseAnalysis
)
from alerts.viewsets.intelligence import (
    AlertCorrelationViewSet, AlertPredictionViewSet, AnomalyDetectionModelViewSet,
    AlertNoiseViewSet, RootCauseAnalysisViewSet, IntelligenceIntegrationViewSet
)

User = get_user_model()


class AlertCorrelationViewSetTest(APITestCase):
    """Test cases for AlertCorrelationViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
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
        
        self.alert_correlation = AlertCorrelation.objects.create(
            name='CPU-Memory Correlation',
            correlation_type='temporal',
            status='confirmed',
            correlation_coefficient=0.85,
            p_value=0.001,
            confidence_level=0.9,
            correlation_strength='strong',
            time_window_minutes=15,
            correlation_threshold=0.8,
            minimum_occurrences=3,
            model_type='statistical'
        )
        
        self.alert_correlation.primary_rules.add(self.alert_rule1, self.alert_rule2)
    
    def test_list_alert_correlations(self):
        """Test listing alert correlations"""
        url = '/api/alerts/intelligence/correlations/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['correlation_type'], 'temporal')
    
    def test_create_alert_correlation(self):
        """Test creating alert correlation"""
        url = '/api/alerts/intelligence/correlations/'
        data = {
            'name': 'Disk-IO Correlation',
            'correlation_type='causal',
            'status='pending',
            'correlation_coefficient': 0.75,
            'p_value': 0.01,
            'confidence_level': 0.8,
            'correlation_strength='medium',
            'time_window_minutes=30,
            'correlation_threshold=0.7,
            'primary_rules': [self.alert_rule1.id, self.alert_rule2.id]
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AlertCorrelation.objects.count(), 2)
    
    def test_retrieve_alert_correlation(self):
        """Test retrieving single alert correlation"""
        url = f'/api/alerts/intelligence/correlations/{self.alert_correlation.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'CPU-Memory Correlation')
    
    def test_analyze_correlation(self):
        """Test analyzing correlation"""
        # Create some test data
        for i in range(10):
            AlertLog.objects.create(
                rule=self.alert_rule1,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'CPU alert {i}'
            )
            
            AlertLog.objects.create(
                rule=self.alert_rule2,
                trigger_value=90.0 + i,
                threshold_value=85.0,
                message=f'Memory alert {i}'
            )
        
        url = f'/api/alerts/intelligence/correlations/{self.alert_correlation.id}/analyze/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('analysis_result', response.data)
        self.assertIn('correlation_coefficient', response.data)
    
    def test_predict_correlation(self):
        """Test predicting correlation"""
        # Create some historical data
        for i in range(20):
            AlertLog.objects.create(
                rule=self.alert_rule1,
                trigger_value=85.0 + (i % 10),
                threshold_value=80.0,
                triggered_at=timezone.now() - timedelta(minutes=i)
            )
        
        url = f'/api/alerts/intelligence/correlations/{self.alert_correlation.id}/predict/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('prediction_result', response.data)
        self.assertIn('predicted_correlation', response.data)
    
    def test_get_correlations_by_type(self):
        """Test getting correlations by type"""
        url = '/api/alerts/intelligence/correlations/by_type/temporal/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_significant_correlations(self):
        """Test getting significant correlations"""
        url = '/api/alerts/intelligence/correlations/significant/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('significant_correlations', response.data)


class AlertPredictionViewSetTest(APITestCase):
    """Test cases for AlertPredictionViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.alert_prediction = AlertPrediction.objects.create(
            name='CPU Usage Prediction',
            prediction_type='threshold_breach',
            model_type='linear_regression',
            is_active=True,
            training_status='completed',
            prediction_horizon_hours=24,
            model_parameters={
                'algorithm': 'linear_regression',
                'features': ['cpu_usage', 'memory_usage']
            }
        )
        
        self.alert_prediction.target_rules.add(self.alert_rule)
    
    def test_list_alert_predictions(self):
        """Test listing alert predictions"""
        url = '/api/alerts/intelligence/predictions/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['prediction_type'], 'threshold_breach')
    
    def test_create_alert_prediction(self):
        """Test creating alert prediction"""
        url = '/api/alerts/intelligence/predictions/'
        data = {
            'name': 'Memory Usage Prediction',
            'prediction_type='volume_forecast',
            'model_type='random_forest',
            'is_active=True,
            'training_status='pending',
            'prediction_horizon_hours=48,
            'target_rules': [self.alert_rule.id]
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AlertPrediction.objects.count(), 2)
    
    def test_retrieve_alert_prediction(self):
        """Test retrieving single alert prediction"""
        url = f'/api/alerts/intelligence/predictions/{self.alert_prediction.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'CPU Usage Prediction')
    
    def test_train_prediction_model(self):
        """Test training prediction model"""
        # Create some training data
        for i in range(100):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=75.0 + (i % 20),
                threshold_value=80.0,
                message=f'Alert {i}',
                triggered_at=timezone.now() - timedelta(hours=i)
            )
        
        url = f'/api/alerts/intelligence/predictions/{self.alert_prediction.id}/train/'
        data = {
            'training_data_days': 30,
            'validation_split': 0.2
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('training_result', response.data)
        self.assertIn('accuracy_score', response.data)
    
    def test_predict_alert(self):
        """Test predicting alert"""
        features = {
            'cpu_usage': 85.0,
            'memory_usage': 70.0
        }
        
        url = f'/api/alerts/intelligence/predictions/{self.alert_prediction.id}/predict/'
        response = self.client.post(url, features)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('prediction_result', response.data)
        self.assertIn('predicted_value', response.data)
    
    def test_evaluate_prediction_model(self):
        """Test evaluating prediction model"""
        # Create test data
        for i in range(50):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=75.0 + (i % 15),
                threshold_value=80.0,
                message=f'Alert {i}',
                triggered_at=timezone.now() - timedelta(hours=i)
            )
        
        url = f'/api/alerts/intelligence/predictions/{self.alert_prediction.id}/evaluate/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('evaluation_result', response.data)
        self.assertIn('accuracy_score', response.data)
    
    def test_get_predictions_by_type(self):
        """Test getting predictions by type"""
        url = '/api/alerts/intelligence/predictions/by_type/threshold_breach/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_active_predictions(self):
        """Test getting active predictions"""
        url = '/api/alerts/intelligence/predictions/active/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class AnomalyDetectionModelViewSetTest(APITestCase):
    """Test cases for AnomalyDetectionModelViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.anomaly_model = AnomalyDetectionModel.objects.create(
            name='CPU Anomaly Detection',
            detection_method='statistical',
            target_anomaly_types=['spike', 'drift', 'outlier'],
            is_active=True,
            sensitivity=0.8,
            window_size_minutes=60,
            baseline_days=7,
            anomaly_threshold=2.0
        )
        
        self.anomaly_model.target_rules.add(self.alert_rule)
    
    def test_list_anomaly_models(self):
        """Test listing anomaly models"""
        url = '/api/alerts/intelligence/anomaly_models/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['detection_method'], 'statistical')
    
    def test_create_anomaly_model(self):
        """Test creating anomaly model"""
        url = '/api/alerts/intelligence/anomaly_models/'
        data = {
            'name': 'Memory Anomaly Detection',
            'detection_method='machine_learning',
            'target_anomaly_types=['spike', 'drift'],
            'is_active=True,
            'sensitivity=0.9,
            'target_rules': [self.alert_rule.id]
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AnomalyDetectionModel.objects.count(), 2)
    
    def test_retrieve_anomaly_model(self):
        """Test retrieving single anomaly model"""
        url = f'/api/alerts/intelligence/anomaly_models/{self.anomaly_model.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'CPU Anomaly Detection')
    
    def test_detect_anomalies(self):
        """Test detecting anomalies"""
        # Create some test data
        data_points = []
        for i in range(100):
            value = 50.0 + (i % 10)
            if i % 20 == 0:  # Add anomaly every 20 points
                value = 100.0
            data_points.append(value)
        
        url = f'/api/alerts/intelligence/anomaly_models/{self.anomaly_model.id}/detect/'
        data = {
            'data_points': data_points
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('anomalies', response.data)
        self.assertIsInstance(response.data['anomalies'], list)
    
    def test_train_anomaly_model(self):
        """Test training anomaly model"""
        # Create training data
        training_data = []
        for i in range(1000):
            training_data.append(50.0 + (i % 20))
        
        url = f'/api/alerts/intelligence/anomaly_models/{self.anomaly_model.id}/train/'
        data = {
            'training_data': training_data
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('training_result', response.data)
        self.assertIn('model_accuracy', response.data)
    
    def test_update_thresholds(self):
        """Test updating thresholds"""
        url = f'/api/alerts/intelligence/anomaly_models/{self.anomaly_model.id}/update_thresholds/'
        data = {
            'new_threshold': 2.5,
            'new_sensitivity': 0.9
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.anomaly_model.refresh_from_db()
        self.assertEqual(self.anomaly_model.anomaly_threshold, 2.5)
        self.assertEqual(self.anomaly_model.sensitivity, 0.9)
    
    def test_get_models_by_method(self):
        """Test getting models by method"""
        url = '/api/alerts/intelligence/anomaly_models/by_method/statistical/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_active_models(self):
        """Test getting active models"""
        url = '/api/alerts/intelligence/anomaly_models/active/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class AlertNoiseViewSetTest(APITestCase):
    """Test cases for AlertNoiseViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='low',
            threshold_value=80.0
        )
        
        self.alert_noise = AlertNoise.objects.create(
            name='CPU Noise Filter',
            noise_type='suppression',
            action='suppress',
            is_active=True,
            target_rules=self.alert_rule,
            message_patterns=['test', 'debug', 'maintenance'],
            severity_filter=['low'],
            source_filter='test-environment',
            suppression_duration_minutes=60
        )
    
    def test_list_alert_noise(self):
        """Test listing alert noise"""
        url = '/api/alerts/intelligence/noise_filters/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['noise_type'], 'suppression')
    
    def test_create_alert_noise(self):
        """Test creating alert noise"""
        url = '/api/alerts/intelligence/noise_filters/'
        data = {
            'name': 'Memory Noise Filter',
            'noise_type='grouping',
            'action='group',
            'is_active=True,
            'target_rules': [self.alert_rule.id],
            'message_patterns=['test', 'debug'],
            'group_window_minutes=15,
            'max_group_size=5
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AlertNoise.objects.count(), 2)
    
    def test_retrieve_alert_noise(self):
        """Test retrieving single alert noise"""
        url = f'/api/alerts/intelligence/noise_filters/{self.alert_noise.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'CPU Noise Filter')
    
    def test_should_filter_alert(self):
        """Test filtering alert"""
        # Create test alert
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert for debugging'
        )
        
        url = f'/api/alerts/intelligence/noise_filters/{self.alert_noise.id}/should_filter/'
        data = {
            'alert_id': alert.id
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('should_filter', response.data)
        self.assertIn('reason', response.data)
    
    def test_filter_alert(self):
        """Test filtering alert"""
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert'
        )
        
        url = f'/api/alerts/intelligence/noise_filters/{self.alert_noise.id}/filter/'
        data = {
            'alert_id': alert.id
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('filter_result', response.data)
        self.assertIn('action', response.data)
    
    def test_get_noise_by_type(self):
        """Test getting noise by type"""
        url = '/api/alerts/intelligence/noise_filters/by_type/suppression/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_active_filters(self):
        """Test getting active filters"""
        url = '/api/alerts/intelligence/noise_filters/active/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_effectiveness_score(self):
        """Test getting effectiveness score"""
        # Set some processed data
        self.alert_noise.total_processed = 100
        self.alert_noise.total_suppressed = 80
        self.alert_noise.save()
        
        url = f'/api/alerts/intelligence/noise_filters/{self.alert_noise.id}/effectiveness/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('effectiveness_score', response.data)


class RootCauseAnalysisViewSetTest(APITestCase):
    """Test cases for RootCauseAnalysisViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='Database Alert',
            alert_type='database_error',
            severity='critical',
            threshold_value=1.0
        )
        
        self.root_cause_analysis = RootCauseAnalysis.objects.create(
            title='Database Connection Failure RCA',
            analysis_method='5_why',
            confidence_level='high',
            status='completed',
            created_by=self.user,
            target_alerts=self.alert_rule
        )
    
    def test_list_root_cause_analyses(self):
        """Test listing root cause analyses"""
        url = '/api/alerts/intelligence/rca/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['analysis_method'], '5_why')
    
    def test_create_root_cause_analysis(self):
        """Test creating root cause analysis"""
        url = '/api/alerts/intelligence/rca/'
        data = {
            'title': 'API Response Time RCA',
            'analysis_method='fishbone',
            'confidence_level='medium',
            'status='draft',
            'created_by': self.user.id,
            'target_alerts': [self.alert_rule.id]
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RootCauseAnalysis.objects.count(), 2)
    
    def test_retrieve_root_cause_analysis(self):
        """Test retrieving single root cause analysis"""
        url = f'/api/alerts/intelligence/rca/{self.root_cause_analysis.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Database Connection Failure RCA')
    
    def test_analyze_root_cause(self):
        """Test analyzing root cause"""
        # Create some alert data for analysis
        for i in range(10):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=1.0 + i,
                threshold_value=1.0,
                message=f'Database error {i}',
                details={'error_code': f'ERR_{i}'}
            )
        
        url = f'/api/alerts/intelligence/rca/{self.root_cause_analysis.id}/analyze/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('analysis_result', response.data)
        self.assertIn('root_causes', response.data)
    
    def test_generate_recommendations(self):
        """Test generating recommendations"""
        # Set some analysis data
        self.root_cause_analysis.root_causes = 'Database connection pool exhausted'
        self.root_cause_analysis.contributing_factors = 'High load, insufficient monitoring'
        self.root_cause_analysis.save()
        
        url = f'/api/alerts/intelligence/rca/{self.root_cause_analysis.id}/recommendations/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recommendations', response.data)
        self.assertIsInstance(response.data['recommendations'], list)
    
    def test_submit_for_review(self):
        """Test submitting for review"""
        reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='testpass123'
        )
        
        url = f'/api/alerts/intelligence/rca/{self.root_cause_analysis.id}/submit_for_review/'
        data = {
            'reviewer_id': reviewer.id
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.root_cause_analysis.refresh_from_db()
        self.assertEqual(self.root_cause_analysis.status, 'submitted_for_review')
        self.assertEqual(self.root_cause_analysis.reviewed_by, reviewer)
    
    def test_approve_rca(self):
        """Test approving RCA"""
        reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='testpass123'
        )
        
        url = f'/api/alerts/intelligence/rca/{self.root_cause_analysis.id}/approve/'
        data = {
            'reviewer_id': reviewer.id,
            'approval_note': 'Analysis is comprehensive'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.root_cause_analysis.refresh_from_db()
        self.assertEqual(self.root_cause_analysis.status, 'approved')
        self.assertEqual(self.root_cause_analysis.approved_by, reviewer)
    
    def test_get_rca_by_method(self):
        """Test getting RCA by method"""
        url = '/api/alerts/intelligence/rca/by_method/5_why/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_rca_by_status(self):
        """Test getting RCA by status"""
        url = '/api/alerts/intelligence/rca/by_status/completed/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class IntelligenceIntegrationViewSetTest(APITestCase):
    """Test cases for IntelligenceIntegrationViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_get_intelligence_overview(self):
        """Test getting intelligence overview"""
        url = '/api/alerts/intelligence/overview/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('correlations', response.data)
        self.assertIn('predictions', response.data)
        self.assertIn('anomaly_models', response.data)
        self.assertIn('noise_filters', response.data)
        self.assertIn('rca_analyses', response.data)
    
    def test_get_intelligence_metrics(self):
        """Test getting intelligence metrics"""
        url = '/api/alerts/intelligence/metrics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_correlations', response.data)
        self.assertIn('active_predictions', response.data)
        self.assertIn('anomaly_detection_rate', response.data)
        self.assertIn('noise_filtering_rate', response.data)
    
    def test_run_intelligence_analysis(self):
        """Test running intelligence analysis"""
        url = '/api/alerts/intelligence/analyze/'
        data = {
            'analysis_type': 'comprehensive',
            'time_range_hours': 24,
            'include_correlations': True,
            'include_predictions': True,
            'include_anomalies': True
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('analysis_result', response.data)
        self.assertIn('correlations_found', response.data)
        self.assertIn('predictions_made', response.data)
    
    def test_get_intelligence_health(self):
        """Test getting intelligence health"""
        url = '/api/alerts/intelligence/health/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('correlation_health', response.data)
        self.assertIn('prediction_health', response.data)
        self.assertIn('anomaly_detection_health', response.data)
    
    def test_get_intelligence_recommendations(self):
        """Test getting intelligence recommendations"""
        url = '/api/alerts/intelligence/recommendations/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recommendations', response.data)
        self.assertIsInstance(response.data['recommendations'], list)
    
    def test_get_intelligence_trends(self):
        """Test getting intelligence trends"""
        url = '/api/alerts/intelligence/trends/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('correlation_trends', response.data)
        self.assertIn('prediction_accuracy_trends', response.data)
        self.assertIn('anomaly_detection_trends', response.data)
