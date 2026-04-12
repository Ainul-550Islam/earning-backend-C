"""
Tests for Intelligence Models
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog
from alerts.models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel, AlertNoise, RootCauseAnalysis
)


class AlertCorrelationModelTest(TestCase):
    """Test cases for AlertCorrelation model"""
    
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
            model_type='statistical',
            model_parameters={'window_size': 15, 'method': 'pearson'}
        )
        
        self.alert_correlation.primary_rules.add(self.alert_rule1, self.alert_rule2)
    
    def test_alert_correlation_creation(self):
        """Test AlertCorrelation creation"""
        self.assertEqual(self.alert_correlation.name, 'CPU-Memory Correlation')
        self.assertEqual(self.alert_correlation.correlation_type, 'temporal')
        self.assertEqual(self.alert_correlation.status, 'confirmed')
        self.assertEqual(self.alert_correlation.correlation_coefficient, 0.85)
        self.assertEqual(self.alert_correlation.confidence_level, 0.9)
        self.assertEqual(self.alert_correlation.correlation_strength, 'strong')
    
    def test_alert_correlation_str_representation(self):
        """Test AlertCorrelation string representation"""
        expected = f'AlertCorrelation: {self.alert_correlation.name} - temporal'
        self.assertEqual(str(self.alert_correlation), expected)
    
    def test_alert_correlation_get_type_display(self):
        """Test AlertCorrelation type display"""
        self.assertEqual(self.alert_correlation.get_type_display(), 'Temporal')
        
        self.alert_correlation.correlation_type = 'causal'
        self.assertEqual(self.alert_correlation.get_type_display(), 'Causal')
        
        self.alert_correlation.correlation_type = 'pattern'
        self.assertEqual(self.alert_correlation.get_type_display(), 'Pattern')
        
        self.alert_correlation.correlation_type = 'statistical'
        self.assertEqual(self.alert_correlation.get_type_display(), 'Statistical')
    
    def test_alert_correlation_get_status_display(self):
        """Test AlertCorrelation status display"""
        self.assertEqual(self.alert_correlation.get_status_display(), 'Confirmed')
        
        self.alert_correlation.status = 'pending'
        self.assertEqual(self.alert_correlation.get_status_display(), 'Pending')
        
        self.alert_correlation.status = 'analyzing'
        self.assertEqual(self.alert_correlation.get_status_display(), 'Analyzing')
        
        self.alert_correlation.status = 'rejected'
        self.assertEqual(self.alert_correlation.get_status_display(), 'Rejected')
        
        self.alert_correlation.status = 'expired'
        self.assertEqual(self.alert_correlation.get_status_display(), 'Expired')
    
    def test_alert_correlation_analyze(self):
        """Test AlertCorrelation analyze method"""
        # Create some alert logs for analysis
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
        
        # Analyze correlation
        result = self.alert_correlation.analyze()
        
        # Should return analysis results
        self.assertIsInstance(result, dict)
        self.assertIn('correlation_coefficient', result)
        self.assertIn('p_value', result)
        self.assertIn('confidence_level', result)
    
    def test_alert_correlation_predict_correlation(self):
        """Test AlertCorrelation predict correlation method"""
        # Create some historical data
        for i in range(20):
            AlertLog.objects.create(
                rule=self.alert_rule1,
                trigger_value=85.0 + (i % 10),
                threshold_value=80.0,
                triggered_at=timezone.now() - timedelta(minutes=i)
            )
        
        # Predict correlation
        prediction = self.alert_correlation.predict_correlation()
        
        # Should return prediction results
        self.assertIsInstance(prediction, dict)
        self.assertIn('predicted_correlation', prediction)
        self.assertIn('confidence', prediction)
    
    def test_alert_correlation_get_primary_rules_count(self):
        """Test AlertCorrelation primary rules count"""
        count = self.alert_correlation.get_primary_rules_count()
        self.assertEqual(count, 2)
        
        # Add another rule
        alert_rule3 = AlertRule.objects.create(
            name='Disk Alert',
            alert_type='disk_usage',
            severity='medium',
            threshold_value=90.0
        )
        self.alert_correlation.primary_rules.add(alert_rule3)
        
        count = self.alert_correlation.get_primary_rules_count()
        self.assertEqual(count, 3)
    
    def test_alert_correlation_get_secondary_rules_count(self):
        """Test AlertCorrelation secondary rules count"""
        # Initially no secondary rules
        count = self.alert_correlation.get_secondary_rules_count()
        self.assertEqual(count, 0)
        
        # Add secondary rules
        alert_rule3 = AlertRule.objects.create(
            name='Disk Alert',
            alert_type='disk_usage',
            severity='medium',
            threshold_value=90.0
        )
        self.alert_correlation.secondary_rules.add(alert_rule3)
        
        count = self.alert_correlation.get_secondary_rules_count()
        self.assertEqual(count, 1)
    
    def test_alert_correlation_is_significant(self):
        """Test AlertCorrelation significance check"""
        # Strong correlation should be significant
        self.assertTrue(self.alert_correlation.is_significant())
        
        # Weak correlation
        self.alert_correlation.correlation_coefficient = 0.3
        self.alert_correlation.save()
        self.assertFalse(self.alert_correlation.is_significant())
    
    def test_alert_correlation_update_confidence(self):
        """Test AlertCorrelation confidence update"""
        new_confidence = 0.95
        new_coefficient = 0.92
        new_p_value = 0.0001
        
        self.alert_correlation.update_confidence(new_confidence, new_coefficient, new_p_value)
        
        self.assertEqual(self.alert_correlation.confidence_level, new_confidence)
        self.assertEqual(self.alert_correlation.correlation_coefficient, new_coefficient)
        self.assertEqual(self.alert_correlation.p_value, new_p_value)


class AlertPredictionModelTest(TestCase):
    """Test cases for AlertPrediction model"""
    
    def setUp(self):
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
            target_rules=self.alert_rule,
            training_days=30,
            prediction_horizon_hours=24,
            model_parameters={
                'algorithm': 'linear_regression',
                'features': ['cpu_usage', 'memory_usage', 'disk_io'],
                'target': 'cpu_usage'
            },
            feature_columns=['cpu_usage', 'memory_usage', 'disk_io']
        )
    
    def test_alert_prediction_creation(self):
        """Test AlertPrediction creation"""
        self.assertEqual(self.alert_prediction.name, 'CPU Usage Prediction')
        self.assertEqual(self.alert_prediction.prediction_type, 'threshold_breach')
        self.assertEqual(self.alert_prediction.model_type, 'linear_regression')
        self.assertEqual(self.alert_prediction.training_status, 'completed')
        self.assertEqual(self.alert_prediction.target_rules.count(), 1)
    
    def test_alert_prediction_str_representation(self):
        """Test AlertPrediction string representation"""
        expected = f'AlertPrediction: {self.alert_prediction.name} - threshold_breach'
        self.assertEqual(str(self.alert_prediction), expected)
    
    def test_alert_prediction_get_type_display(self):
        """Test AlertPrediction type display"""
        self.assertEqual(self.alert_prediction.get_type_display(), 'Threshold Breach')
        
        self.alert_prediction.prediction_type = 'volume_forecast'
        self.assertEqual(self.alert_prediction.get_type_display(), 'Volume Forecast')
        
        self.alert_prediction.prediction_type = 'severity_prediction'
        self.assertEqual(self.alert_prediction.get_type_display(), 'Severity Prediction')
        
        self.alert_prediction.prediction_type = 'trend_analysis'
        self.assertEqual(self.alert_prediction.get_type_display(), 'Trend Analysis')
    
    def test_alert_prediction_get_model_type_display(self):
        """Test AlertPrediction model type display"""
        self.assertEqual(self.alert_prediction.get_model_type_display(), 'Linear Regression')
        
        self.alert_prediction.model_type = 'random_forest'
        self.assertEqual(self.alert_prediction.get_model_type_display(), 'Random Forest')
        
        self.alert_prediction.model_type = 'neural_network'
        self.assertEqual(self.alert_prediction.get_model_type_display(), 'Neural Network')
        
        self.alert_prediction.model_type = 'time_series'
        self.assertEqual(self.alert_prediction.get_model_type_display(), 'Time Series')
    
    def test_alert_prediction_get_training_status_display(self):
        """Test AlertPrediction training status display"""
        self.assertEqual(self.alert_prediction.get_training_status_display(), 'Completed')
        
        self.alert_prediction.training_status = 'pending'
        self.assertEqual(self.alert_prediction.get_training_status_display(), 'Pending')
        
        self.alert_prediction.training_status = 'training'
        self.assertEqual(self.alert_prediction.get_training_status_display(), 'Training')
        
        self.alert_prediction.training_status = 'failed'
        self.assertEqual(self.alert_prediction.get_training_status_display(), 'Failed')
        
        self.alert_prediction.training_status = 'updating'
        self.assertEqual(self.alert_prediction.get_training_status_display(), 'Updating')
    
    def test_alert_prediction_train(self):
        """Test AlertPrediction train method"""
        # Create some training data
        for i in range(100):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=75.0 + (i % 20),
                threshold_value=80.0,
                message=f'Alert {i}',
                triggered_at=timezone.now() - timedelta(hours=i)
            )
        
        # Train model
        result = self.alert_prediction.train()
        
        # Should return training results
        self.assertIsInstance(result, dict)
        self.assertIn('accuracy_score', result)
        self.assertIn('precision_score', result)
        self.assertIn('recall_score', result)
        self.assertIn('f1_score', result)
    
    def test_alert_prediction_predict(self):
        """Test AlertPrediction predict method"""
        # Create some test data
        features = {
            'cpu_usage': 85.0,
            'memory_usage': 70.0,
            'disk_io': 50.0
        }
        
        prediction = self.alert_prediction.predict(features)
        
        # Should return prediction results
        self.assertIsInstance(prediction, dict)
        self.assertIn('predicted_value', prediction)
        self.assertIn('confidence', prediction)
        self.assertIn('prediction_time', prediction)
    
    def test_alert_prediction_evaluate(self):
        """Test AlertPrediction evaluate method"""
        # Create test data
        for i in range(50):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=75.0 + (i % 15),
                threshold_value=80.0,
                message=f'Alert {i}',
                triggered_at=timezone.now() - timedelta(hours=i)
            )
        
        # Evaluate model
        evaluation = self.alert_prediction.evaluate()
        
        # Should return evaluation results
        self.assertIsInstance(evaluation, dict)
        self.assertIn('accuracy_score', evaluation)
        self.assertIn('precision_score', evaluation)
        self.assertIn('recall_score', evaluation)
        self.assertIn('f1_score', evaluation)
        self.assertIn('mean_absolute_error', evaluation)
    
    def test_alert_prediction_get_target_rules_count(self):
        """Test AlertPrediction target rules count"""
        count = self.alert_prediction.get_target_rules_count()
        self.assertEqual(count, 1)
        
        # Add another rule
        alert_rule2 = AlertRule.objects.create(
            name='Memory Alert',
            alert_type='memory_usage',
            severity='medium',
            threshold_value=85.0
        )
        self.alert_prediction.target_rules.add(alert_rule2)
        
        count = self.alert_prediction.get_target_rules_count()
        self.assertEqual(count, 2)
    
    def test_alert_prediction_is_ready(self):
        """Test AlertPrediction readiness check"""
        # Completed training should be ready
        self.assertTrue(self.alert_prediction.is_ready())
        
        # Pending training should not be ready
        self.alert_prediction.training_status = 'pending'
        self.assertFalse(self.alert_prediction.is_ready())
        
        # Failed training should not be ready
        self.alert_prediction.training_status = 'failed'
        self.assertFalse(self.alert_prediction.is_ready())
    
    def test_alert_prediction_get_accuracy_score(self):
        """Test AlertPrediction accuracy score"""
        # Initially should be None
        self.assertIsNone(self.alert_prediction.get_accuracy_score())
        
        # Set accuracy score
        self.alert_prediction.accuracy_score = 0.85
        self.alert_prediction.save()
        
        score = self.alert_prediction.get_accuracy_score()
        self.assertEqual(score, 0.85)


class AnomalyDetectionModelModelTest(TestCase):
    """Test cases for AnomalyDetectionModel model"""
    
    def setUp(self):
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
            anomaly_threshold=2.0,
            min_alert_count=3,
            model_parameters={
                'algorithm': 'z_score',
                'threshold': 2.0,
                'window_size': 60
            }
        )
        
        self.anomaly_model.target_rules.add(self.alert_rule)
    
    def test_anomaly_detection_model_creation(self):
        """Test AnomalyDetectionModel creation"""
        self.assertEqual(self.anomaly_model.name, 'CPU Anomaly Detection')
        self.assertEqual(self.anomaly_model.detection_method, 'statistical')
        self.assertEqual(self.anomaly_model.sensitivity, 0.8)
        self.assertEqual(self.anomaly_model.window_size_minutes, 60)
        self.assertEqual(self.anomaly_model.baseline_days, 7)
        self.assertEqual(self.anomaly_model.anomaly_threshold, 2.0)
    
    def test_anomaly_detection_model_str_representation(self):
        """Test AnomalyDetectionModel string representation"""
        expected = f'AnomalyDetectionModel: {self.anomaly_model.name} - statistical'
        self.assertEqual(str(self.anomaly_model), expected)
    
    def test_anomaly_detection_model_get_method_display(self):
        """Test AnomalyDetectionModel method display"""
        self.assertEqual(self.anomaly_model.get_method_display(), 'Statistical')
        
        self.anomaly_model.detection_method = 'machine_learning'
        self.assertEqual(self.anomaly_model.get_method_display(), 'Machine Learning')
        
        self.anomaly_model.detection_method = 'hybrid'
        self.assertEqual(self.anomaly_model.get_method_display(), 'Hybrid')
        
        self.anomaly_model.detection_method = 'time_series'
        self.assertEqual(self.anomaly_model.get_method_display(), 'Time Series')
    
    def test_anomaly_detection_model_detect_anomalies(self):
        """Test AnomalyDetectionModel detect anomalies method"""
        # Create some test data
        data_points = []
        for i in range(100):
            # Normal data with some anomalies
            value = 50.0 + (i % 10)
            if i % 20 == 0:  # Add anomaly every 20 points
                value = 100.0
            data_points.append(value)
        
        anomalies = self.anomaly_model.detect_anomalies(data_points)
        
        # Should return list of anomalies
        self.assertIsInstance(anomalies, list)
        for anomaly in anomalies:
            self.assertIsInstance(anomaly, dict)
            self.assertIn('index', anomaly)
            self.assertIn('value', anomaly)
            self.assertIn('anomaly_score', anomaly)
    
    def test_anomaly_detection_model_train(self):
        """Test AnomalyDetectionModel train method"""
        # Create training data
        training_data = []
        for i in range(1000):
            training_data.append(50.0 + (i % 20))
        
        # Train model
        result = self.anomaly_model.train(training_data)
        
        # Should return training results
        self.assertIsInstance(result, dict)
        self.assertIn('training_samples', result)
        self.assertIn('model_accuracy', result)
        self.assertIn('false_positive_rate', result)
    
    def test_anomaly_detection_model_update_thresholds(self):
        """Test AnomalyDetectionModel update thresholds method"""
        new_threshold = 2.5
        new_sensitivity = 0.9
        
        self.anomaly_model.update_thresholds(new_threshold, new_sensitivity)
        
        self.assertEqual(self.anomaly_model.anomaly_threshold, new_threshold)
        self.assertEqual(self.anomaly_model.sensitivity, new_sensitivity)
    
    def test_anomaly_detection_model_get_target_rules_count(self):
        """Test AnomalyDetectionModel target rules count"""
        count = self.anomaly_model.get_target_rules_count()
        self.assertEqual(count, 1)
        
        # Add another rule
        alert_rule2 = AlertRule.objects.create(
            name='Memory Alert',
            alert_type='memory_usage',
            severity='medium',
            threshold_value=85.0
        )
        self.anomaly_model.target_rules.add(alert_rule2)
        
        count = self.anomaly_model.get_target_rules_count()
        self.assertEqual(count, 2)
    
    def test_anomaly_detection_model_is_anomaly(self):
        """Test AnomalyDetectionModel anomaly detection"""
        # Normal value
        is_anomaly = self.anomaly_model.is_anomaly(55.0)
        self.assertFalse(is_anomaly)
        
        # Anomalous value
        is_anomaly = self.anomaly_model.is_anomaly(100.0)
        self.assertTrue(is_anomaly)
    
    def test_anomaly_detection_model_get_anomaly_score(self):
        """Test AnomalyDetectionModel anomaly score calculation"""
        # Normal value
        score = self.anomaly_model.get_anomaly_score(55.0)
        self.assertIsInstance(score, float)
        self.assertLess(score, self.anomaly_model.anomaly_threshold)
        
        # Anomalous value
        score = self.anomaly_model.get_anomaly_score(100.0)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, self.anomaly_model.anomaly_threshold)


class AlertNoiseModelTest(TestCase):
    """Test cases for AlertNoise model"""
    
    def setUp(self):
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
            suppression_duration_minutes=60,
            max_suppressions_per_hour=10,
            group_window_minutes=15,
            max_group_size=5
        )
    
    def test_alert_noise_creation(self):
        """Test AlertNoise creation"""
        self.assertEqual(self.alert_noise.name, 'CPU Noise Filter')
        self.assertEqual(self.alert_noise.noise_type, 'suppression')
        self.assertEqual(self.alert_noise.action, 'suppress')
        self.assertEqual(self.alert_noise.target_rules.count(), 1)
        self.assertIsInstance(self.alert_noise.message_patterns, list)
    
    def test_alert_noise_str_representation(self):
        """Test AlertNoise string representation"""
        expected = f'AlertNoise: {self.alert_noise.name} - suppression'
        self.assertEqual(str(self.alert_noise), expected)
    
    def test_alert_noise_get_type_display(self):
        """Test AlertNoise type display"""
        self.assertEqual(self.alert_noise.get_type_display(), 'Suppression')
        
        self.alert_noise.noise_type = 'grouping'
        self.assertEqual(self.alert_noise.get_type_display(), 'Grouping')
        
        self.alert_noise.noise_type = 'delay'
        self.assertEqual(self.alert_noise.get_type_display(), 'Delay')
        
        self.alert_noise.noise_type = 'prioritization'
        self.assertEqual(self.alert_noise.get_type_display(), 'Prioritization')
    
    def test_alert_noise_get_action_display(self):
        """Test AlertNoise action display"""
        self.assertEqual(self.alert_noise.get_action_display(), 'Suppress')
        
        self.alert_noise.action = 'group'
        self.assertEqual(self.alert_noise.get_action_display(), 'Group')
        
        self.alert_noise.action = 'delay'
        self.assertEqual(self.alert_noise.get_action_display(), 'Delay')
        
        self.alert_noise.action = 'modify'
        self.assertEqual(self.alert_noise.get_action_display(), 'Modify')
    
    def test_alert_noise_should_filter(self):
        """Test AlertNoise should filter logic"""
        # Create test alert
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert for debugging'
        )
        
        # Should filter due to message pattern
        should_filter = self.alert_noise.should_filter(alert)
        self.assertTrue(should_filter)
        
        # Should not filter different message
        alert.message = 'Production alert'
        should_filter = self.alert_noise.should_filter(alert)
        self.assertFalse(should_filter)
    
    def test_alert_noise_filter_alert(self):
        """Test AlertNoise filter alert method"""
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert'
        )
        
        # Filter the alert
        result = self.alert_noise.filter_alert(alert)
        
        # Should return result indicating filtering action
        self.assertIsInstance(result, dict)
        self.assertIn('filtered', result)
        self.assertIn('action', result)
        self.assertIn('reason', result)
    
    def test_alert_noise_get_target_rules_count(self):
        """Test AlertNoise target rules count"""
        count = self.alert_noise.get_target_rules_count()
        self.assertEqual(count, 1)
        
        # Add another rule
        alert_rule2 = AlertRule.objects.create(
            name='Memory Alert',
            alert_type='memory_usage',
            severity='low',
            threshold_value=85.0
        )
        self.alert_noise.target_rules.add(alert_rule2)
        
        count = self.alert_noise.get_target_rules_count()
        self.assertEqual(count, 2)
    
    def test_alert_noise_get_effectiveness_score(self):
        """Test AlertNoise effectiveness score calculation"""
        # Initially no data
        score = self.alert_noise.get_effectiveness_score()
        self.assertEqual(score, 0)
        
        # Add some processed data
        self.alert_noise.total_processed = 100
        self.alert_noise.total_suppressed = 80
        self.alert_noise.save()
        
        score = self.alert_noise.get_effectiveness_score()
        expected = (80 / 100) * 100  # 80% effectiveness
        self.assertEqual(score, expected)
    
    def test_alert_noise_update_statistics(self):
        """Test AlertNoise statistics update"""
        # Update statistics
        self.alert_noise.update_statistics(
            processed=50,
            suppressed=30,
            grouped=10,
            delayed=5
        )
        
        self.assertEqual(self.alert_noise.total_processed, 50)
        self.assertEqual(self.alert_noise.total_suppressed, 30)
        self.assertEqual(self.alert_noise.total_grouped, 10)
        self.assertEqual(self.alert_noise.total_delayed, 5)
    
    def test_alert_noise_reset_statistics(self):
        """Test AlertNoise statistics reset"""
        # Set some statistics
        self.alert_noise.total_processed = 100
        self.alert_noise.total_suppressed = 80
        self.alert_noise.save()
        
        # Reset statistics
        self.alert_noise.reset_statistics()
        
        self.assertEqual(self.alert_noise.total_processed, 0)
        self.assertEqual(self.alert_noise.total_suppressed, 0)
        self.assertEqual(self.alert_noise.total_grouped, 0)
        self.assertEqual(self.alert_noise.total_delayed, 0)


class RootCauseAnalysisModelTest(TestCase):
    """Test cases for RootCauseAnalysis model"""
    
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
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
            internal_only=False,
            created_by=self.user,
            target_alerts=self.alert_rule
        )
    
    def test_root_cause_analysis_creation(self):
        """Test RootCauseAnalysis creation"""
        self.assertEqual(self.root_cause_analysis.title, 'Database Connection Failure RCA')
        self.assertEqual(self.root_cause_analysis.analysis_method, '5_why')
        self.assertEqual(self.root_cause_analysis.confidence_level, 'high')
        self.assertEqual(self.root_cause_analysis.status, 'completed')
        self.assertEqual(self.root_cause_analysis.created_by, self.user)
    
    def test_root_cause_analysis_str_representation(self):
        """Test RootCauseAnalysis string representation"""
        expected = f'RootCauseAnalysis: {self.root_cause_analysis.id} - completed'
        self.assertEqual(str(self.root_cause_analysis), expected)
    
    def test_root_cause_analysis_get_method_display(self):
        """Test RootCauseAnalysis method display"""
        self.assertEqual(self.root_cause_analysis.get_method_display(), '5 Whys')
        
        self.root_cause_analysis.analysis_method = 'fishbone'
        self.assertEqual(self.root_cause_analysis.get_method_display(), 'Fishbone')
        
        self.root_cause_analysis.analysis_method = 'timeline'
        self.assertEqual(self.root_cause_analysis.get_method_display(), 'Timeline')
        
        self.root_cause_analysis.analysis_method = 'expert'
        self.assertEqual(self.root_cause_analysis.get_method_display(), 'Expert')
    
    def test_root_cause_analysis_get_confidence_display(self):
        """Test RootCauseAnalysis confidence display"""
        self.assertEqual(self.root_cause_analysis.get_confidence_display(), 'High')
        
        self.root_cause_analysis.confidence_level = 'medium'
        self.assertEqual(self.root_cause_analysis.get_confidence_display(), 'Medium')
        
        self.root_cause_analysis.confidence_level = 'low'
        self.assertEqual(self.root_cause_analysis.get_confidence_display(), 'Low')
        
        self.root_cause_analysis.confidence_level = 'very_high'
        self.assertEqual(self.root_cause_analysis.get_confidence_display(), 'Very High')
    
    def test_root_cause_analysis_get_status_display(self):
        """Test RootCauseAnalysis status display"""
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'Completed')
        
        self.root_cause_analysis.status = 'draft'
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'Draft')
        
        self.root_cause_analysis.status = 'in_progress'
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'In Progress')
        
        self.root_cause_analysis.status = 'submitted_for_review'
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'Submitted For Review')
        
        self.root_cause_analysis.status = 'approved'
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'Approved')
        
        self.root_cause_analysis.status = 'rejected'
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'Rejected')
    
    def test_root_cause_analysis_analyze(self):
        """Test RootCauseAnalysis analyze method"""
        # Create some alert data for analysis
        for i in range(10):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=1.0 + i,
                threshold_value=1.0,
                message=f'Database error {i}',
                details={'error_code': f'ERR_{i}'}
            )
        
        # Perform analysis
        result = self.root_cause_analysis.analyze()
        
        # Should return analysis results
        self.assertIsInstance(result, dict)
        self.assertIn('root_causes', result)
        self.assertIn('contributing_factors', result)
        self.assertIn('recommendations', result)
    
    def test_root_cause_analysis_generate_recommendations(self):
        """Test RootCauseAnalysis generate recommendations method"""
        # Set some analysis data
        self.root_cause_analysis.root_causes = 'Database connection pool exhausted'
        self.root_cause_analysis.contributing_factors = 'High load, insufficient monitoring'
        self.root_cause_analysis.save()
        
        # Generate recommendations
        recommendations = self.root_cause_analysis.generate_recommendations()
        
        # Should return list of recommendations
        self.assertIsInstance(recommendations, list)
        for recommendation in recommendations:
            self.assertIsInstance(recommendation, str)
    
    def test_root_cause_analysis_get_target_alerts_count(self):
        """Test RootCauseAnalysis target alerts count"""
        count = self.root_cause_analysis.get_target_alerts_count()
        self.assertEqual(count, 1)
        
        # Add another alert
        alert_rule2 = AlertRule.objects.create(
            name='Memory Alert',
            alert_type='memory_error',
            severity='high',
            threshold_value=1.0
        )
        self.root_cause_analysis.target_alerts.add(alert_rule2)
        
        count = self.root_cause_analysis.get_target_alerts_count()
        self.assertEqual(count, 2)
    
    def test_root_cause_analysis_get_analysis_score(self):
        """Test RootCauseAnalysis analysis score calculation"""
        # Initially should be 0
        score = self.root_cause_analysis.get_analysis_score()
        self.assertEqual(score, 0)
        
        # Set some analysis data
        self.root_cause_analysis.root_causes = 'Database connection pool exhausted'
        self.root_cause_analysis.contributing_factors = 'High load, insufficient monitoring'
        self.root_cause_analysis.lessons_learned = 'Need better monitoring'
        self.root_cause_analysis.preventive_measures = 'Increase pool size'
        self.root_cause_analysis.save()
        
        score = self.root_cause_analysis.get_analysis_score()
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)
    
    def test_root_cause_analysis_submit_for_review(self):
        """Test RootCauseAnalysis submit for review method"""
        reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='testpass123'
        )
        
        self.root_cause_analysis.submit_for_review(reviewer)
        
        self.assertEqual(self.root_cause_analysis.status, 'submitted_for_review')
        self.assertEqual(self.root_cause_analysis.reviewed_by, reviewer)
        self.assertIsNotNone(self.root_cause_analysis.reviewed_at)
    
    def test_root_cause_analysis_approve(self):
        """Test RootCauseAnalysis approve method"""
        reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='testpass123'
        )
        
        self.root_cause_analysis.approve(reviewer, 'Analysis is comprehensive')
        
        self.assertEqual(self.root_cause_analysis.status, 'approved')
        self.assertEqual(self.root_cause_analysis.approved_by, reviewer)
        self.assertEqual(self.root_cause_analysis.approval_note, 'Analysis is comprehensive')
        self.assertIsNotNone(self.root_cause_analysis.approved_at)
