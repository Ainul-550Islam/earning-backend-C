"""Tests for Intelligence Models"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from api.alerts.models.core import AlertRule, AlertLog
from api.alerts.models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel, AlertNoise, RootCauseAnalysis
)

User = get_user_model()


class AlertCorrelationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_rule1 = AlertRule.objects.create(
            name='CPU Alert', alert_type='server_error', severity='high',
            threshold_value=80.0, created_by=self.user
        )
        self.alert_rule2 = AlertRule.objects.create(
            name='Memory Alert', alert_type='server_error', severity='high',
            threshold_value=85.0, created_by=self.user
        )
        self.alert_correlation = AlertCorrelation.objects.create(
            name='CPU-Memory Correlation',
            correlation_type='temporal',
            status='confirmed',
            correlation_coefficient=0.85,
            p_value=0.001,
            confidence_level=0.9,
            correlation_strength=0.85,
            time_window_minutes=15,
            correlation_threshold=0.8,
            minimum_occurrences=3,
            model_type='linear',
            model_parameters={'window_size': 15, 'method': 'pearson'}
        )
        self.alert_correlation.primary_rules.add(self.alert_rule1, self.alert_rule2)

    def test_alert_correlation_creation(self):
        self.assertEqual(self.alert_correlation.name, 'CPU-Memory Correlation')
        self.assertEqual(self.alert_correlation.correlation_type, 'temporal')
        self.assertEqual(self.alert_correlation.status, 'confirmed')
        self.assertEqual(self.alert_correlation.correlation_coefficient, 0.85)
        self.assertEqual(self.alert_correlation.confidence_level, 0.9)

    def test_alert_correlation_str_representation(self):
        expected = f'AlertCorrelation: {self.alert_correlation.name} - temporal'
        self.assertEqual(str(self.alert_correlation), expected)

    def test_alert_correlation_get_type_display(self):
        self.assertEqual(self.alert_correlation.profile_type, 'Temporal')
        self.alert_correlation.correlation_type = 'causal'
        self.assertEqual(self.alert_correlation.profile_type, 'Causal')
        self.alert_correlation.correlation_type = 'statistical'
        self.assertEqual(self.alert_correlation.profile_type, 'Statistical')

    def test_alert_correlation_get_status_display(self):
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
        for i in range(5):
            AlertLog.objects.create(
                rule=self.alert_rule1, trigger_value=85.0 + i,
                threshold_value=80.0, message=f'CPU alert {i}'
            )
        result = self.alert_correlation.analyze()
        self.assertIsInstance(result, dict)
        self.assertIn('correlation_coefficient', result)
        self.assertIn('p_value', result)
        self.assertIn('confidence_level', result)

    def test_alert_correlation_predict_correlation(self):
        alert_log = AlertLog.objects.create(
            rule=self.alert_rule1, trigger_value=85.0,
            threshold_value=80.0, message='CPU alert'
        )
        prediction = self.alert_correlation.predict_correlation(alert_log)
        self.assertIsInstance(prediction, bool)

    def test_alert_correlation_get_primary_rules_count(self):
        self.assertEqual(self.alert_correlation.get_primary_rules_count(), 2)
        alert_rule3 = AlertRule.objects.create(
            name='Disk Alert', alert_type='server_down', severity='medium',
            threshold_value=90.0, created_by=self.user
        )
        self.alert_correlation.primary_rules.add(alert_rule3)
        self.assertEqual(self.alert_correlation.get_primary_rules_count(), 3)

    def test_alert_correlation_get_secondary_rules_count(self):
        self.assertEqual(self.alert_correlation.get_secondary_rules_count(), 0)
        alert_rule3 = AlertRule.objects.create(
            name='Disk Alert', alert_type='server_down', severity='medium',
            threshold_value=90.0, created_by=self.user
        )
        self.alert_correlation.secondary_rules.add(alert_rule3)
        self.assertEqual(self.alert_correlation.get_secondary_rules_count(), 1)

    def test_alert_correlation_is_significant(self):
        self.assertTrue(self.alert_correlation.is_significant())
        self.alert_correlation.correlation_coefficient = 0.3
        self.assertFalse(self.alert_correlation.is_significant())

    def test_alert_correlation_update_confidence(self):
        self.alert_correlation.update_confidence(0.95, 0.92, 0.0001)
        self.assertEqual(self.alert_correlation.confidence_level, 0.95)
        self.assertEqual(self.alert_correlation.correlation_coefficient, 0.92)
        self.assertEqual(self.alert_correlation.p_value, 0.0001)


class AlertPredictionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='CPU Alert', alert_type='server_error', severity='high',
            threshold_value=80.0, created_by=self.user
        )
        self.alert_prediction = AlertPrediction.objects.create(
            name='CPU Usage Prediction',
            prediction_type='threshold_breach',
            model_type='linear_regression',
            is_active=True,
            training_status='completed',
            training_days=30,
            prediction_horizon_hours=24,
            model_parameters={'algorithm': 'linear_regression'},
            feature_columns=['cpu', 'memory', 'disk_io']
        )
        self.alert_prediction.target_rules.add(self.alert_rule)

    def test_alert_prediction_creation(self):
        self.assertEqual(self.alert_prediction.name, 'CPU Usage Prediction')
        self.assertEqual(self.alert_prediction.prediction_type, 'threshold_breach')
        self.assertEqual(self.alert_prediction.model_type, 'linear_regression')
        self.assertEqual(self.alert_prediction.training_status, 'completed')
        self.assertEqual(self.alert_prediction.target_rules.count(), 1)

    def test_alert_prediction_str_representation(self):
        expected = f'AlertPrediction: {self.alert_prediction.name} - threshold_breach'
        self.assertEqual(str(self.alert_prediction), expected)

    def test_alert_prediction_get_type_display(self):
        self.assertEqual(self.alert_prediction.profile_type, 'Threshold Breach')
        self.alert_prediction.prediction_type = 'volume_forecast'
        self.assertEqual(self.alert_prediction.profile_type, 'Volume Forecast')
        self.alert_prediction.prediction_type = 'severity_prediction'
        self.assertEqual(self.alert_prediction.profile_type, 'Severity Prediction')
        self.alert_prediction.prediction_type = 'trend_analysis'
        self.assertEqual(self.alert_prediction.profile_type, 'Trend Analysis')

    def test_alert_prediction_get_model_type_display(self):
        self.assertEqual(self.alert_prediction.get_model_type_display(), 'Linear Regression')
        self.alert_prediction.model_type = 'random_forest'
        self.assertEqual(self.alert_prediction.get_model_type_display(), 'Random Forest')
        self.alert_prediction.model_type = 'neural_network'
        self.assertEqual(self.alert_prediction.get_model_type_display(), 'Neural Network')
        self.alert_prediction.model_type = 'time_series'
        self.assertEqual(self.alert_prediction.get_model_type_display(), 'Time Series')

    def test_alert_prediction_get_training_status_display(self):
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
        result = self.alert_prediction.train()
        self.assertIsInstance(result, dict)
        self.assertIn('accuracy_score', result)
        self.assertIn('precision_score', result)
        self.assertIn('recall_score', result)
        self.assertIn('f1_score', result)

    def test_alert_prediction_predict(self):
        features = {'cpu': 85.0, 'memory': 70.0, 'disk_io': 50.0}
        prediction = self.alert_prediction.predict(features)
        self.assertIsInstance(prediction, dict)
        self.assertIn('confidence', prediction)
        self.assertIn('prediction_time', prediction)

    def test_alert_prediction_evaluate(self):
        evaluation = self.alert_prediction.evaluate()
        self.assertIsInstance(evaluation, dict)
        self.assertIn('accuracy_score', evaluation)
        self.assertIn('precision_score', evaluation)
        self.assertIn('recall_score', evaluation)
        self.assertIn('f1_score', evaluation)
        self.assertIn('mean_absolute_error', evaluation)

    def test_alert_prediction_get_target_rules_count(self):
        self.assertEqual(self.alert_prediction.get_target_rules_count(), 1)
        alert_rule2 = AlertRule.objects.create(
            name='Memory Alert', alert_type='server_error', severity='medium',
            threshold_value=85.0, created_by=self.user
        )
        self.alert_prediction.target_rules.add(alert_rule2)
        self.assertEqual(self.alert_prediction.get_target_rules_count(), 2)

    def test_alert_prediction_is_ready(self):
        self.assertTrue(self.alert_prediction.is_ready())
        self.alert_prediction.training_status = 'pending'
        self.assertFalse(self.alert_prediction.is_ready())
        self.alert_prediction.training_status = 'failed'
        self.assertFalse(self.alert_prediction.is_ready())

    def test_alert_prediction_get_accuracy_score(self):
        self.assertIsNone(self.alert_prediction.get_accuracy_score())
        self.alert_prediction.accuracy_score = 0.85
        self.alert_prediction.save()
        self.assertEqual(self.alert_prediction.get_accuracy_score(), 0.85)


class AnomalyDetectionModelModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='CPU Alert', alert_type='server_error', severity='high',
            threshold_value=80.0, created_by=self.user
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
            model_parameters={'algorithm': 'z_score', 'threshold': 2.0}
        )
        self.anomaly_model.target_rules.add(self.alert_rule)

    def test_anomaly_detection_model_creation(self):
        self.assertEqual(self.anomaly_model.name, 'CPU Anomaly Detection')
        self.assertEqual(self.anomaly_model.detection_method, 'statistical')
        self.assertEqual(self.anomaly_model.sensitivity, 0.8)
        self.assertEqual(self.anomaly_model.window_size_minutes, 60)
        self.assertEqual(self.anomaly_model.baseline_days, 7)
        self.assertEqual(self.anomaly_model.anomaly_threshold, 2.0)

    def test_anomaly_detection_model_str_representation(self):
        expected = f'AnomalyDetectionModel: {self.anomaly_model.name} - statistical'
        self.assertEqual(str(self.anomaly_model), expected)

    def test_anomaly_detection_model_get_method_display(self):
        self.assertEqual(self.anomaly_model.get_method_display(), 'Statistical')
        self.anomaly_model.detection_method = 'machine_learning'
        self.assertEqual(self.anomaly_model.get_method_display(), 'Machine Learning')
        self.anomaly_model.detection_method = 'hybrid'
        self.assertEqual(self.anomaly_model.get_method_display(), 'Hybrid')
        self.anomaly_model.detection_method = 'time_series'
        self.assertEqual(self.anomaly_model.get_method_display(), 'Time Series')

    def test_anomaly_detection_model_detect_anomalies(self):
        data_points = []
        for i in range(100):
            value = 50.0 + (i % 10)
            if i % 20 == 0:
                value = 150.0
            data_points.append(value)
        anomalies = self.anomaly_model.detect_anomalies_from_data(data_points)
        self.assertIsInstance(anomalies, list)
        for anomaly in anomalies:
            self.assertIn('index', anomaly)
            self.assertIn('value', anomaly)
            self.assertIn('anomaly_score', anomaly)

    def test_anomaly_detection_model_train(self):
        training_data = [50.0 + (i % 20) for i in range(1000)]
        result = self.anomaly_model.train(training_data)
        self.assertIsInstance(result, dict)
        self.assertIn('training_samples', result)
        self.assertIn('model_accuracy', result)
        self.assertIn('false_positive_rate', result)

    def test_anomaly_detection_model_update_thresholds(self):
        self.anomaly_model.update_thresholds(2.5, 0.9)
        self.assertEqual(self.anomaly_model.anomaly_threshold, 2.5)
        self.assertEqual(self.anomaly_model.sensitivity, 0.9)

    def test_anomaly_detection_model_get_target_rules_count(self):
        self.assertEqual(self.anomaly_model.get_target_rules_count(), 1)
        alert_rule2 = AlertRule.objects.create(
            name='Memory Alert', alert_type='server_error', severity='medium',
            threshold_value=85.0, created_by=self.user
        )
        self.anomaly_model.target_rules.add(alert_rule2)
        self.assertEqual(self.anomaly_model.get_target_rules_count(), 2)

    def test_anomaly_detection_model_is_anomaly(self):
        self.assertFalse(self.anomaly_model.is_anomaly(52.0, 50.0, 5.0))
        self.assertTrue(self.anomaly_model.is_anomaly(100.0, 50.0, 5.0))

    def test_anomaly_detection_model_get_anomaly_score(self):
        score_normal = self.anomaly_model.get_anomaly_score(52.0, 50.0, 5.0)
        self.assertIsInstance(score_normal, float)
        self.assertLess(score_normal, self.anomaly_model.anomaly_threshold)
        score_anomalous = self.anomaly_model.get_anomaly_score(100.0, 50.0, 5.0)
        self.assertIsInstance(score_anomalous, float)
        self.assertGreaterEqual(score_anomalous, self.anomaly_model.anomaly_threshold)


class AlertNoiseModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='CPU Alert', alert_type='server_error', severity='low',
            threshold_value=80.0, created_by=self.user
        )
        self.alert_noise = AlertNoise.objects.create(
            name='CPU Noise Filter',
            noise_type='suppression',
            action='suppress',
            is_active=True,
            message_patterns=['test', 'debug', 'maintenance'],
            severity_filter=['low'],
            source_filter=['test-environment'],
            suppression_duration_minutes=60,
            max_suppressions_per_hour=10,
            group_window_minutes=15,
            max_group_size=5
        )
        self.alert_noise.target_rules.add(self.alert_rule)

    def test_alert_noise_creation(self):
        self.assertEqual(self.alert_noise.name, 'CPU Noise Filter')
        self.assertEqual(self.alert_noise.noise_type, 'suppression')
        self.assertEqual(self.alert_noise.action, 'suppress')
        self.assertEqual(self.alert_noise.target_rules.count(), 1)
        self.assertIsInstance(self.alert_noise.message_patterns, list)

    def test_alert_noise_str_representation(self):
        expected = f'AlertNoise: {self.alert_noise.name} - suppression'
        self.assertEqual(str(self.alert_noise), expected)

    def test_alert_noise_get_type_display(self):
        self.assertEqual(self.alert_noise.profile_type, 'Suppression')
        self.alert_noise.noise_type = 'grouping'
        self.assertEqual(self.alert_noise.profile_type, 'Grouping')
        self.alert_noise.noise_type = 'delay'
        self.assertEqual(self.alert_noise.profile_type, 'Delay')
        self.alert_noise.noise_type = 'prioritization'
        self.assertEqual(self.alert_noise.profile_type, 'Prioritization')

    def test_alert_noise_get_action_display(self):
        self.assertEqual(self.alert_noise.get_action_display(), 'Suppress')
        self.alert_noise.action = 'group'
        self.assertEqual(self.alert_noise.get_action_display(), 'Group')
        self.alert_noise.action = 'delay'
        self.assertEqual(self.alert_noise.get_action_display(), 'Delay')
        self.alert_noise.action = 'modify'
        self.assertEqual(self.alert_noise.get_action_display(), 'Modify')

    def test_alert_noise_should_filter(self):
        alert = AlertLog.objects.create(
            rule=self.alert_rule, trigger_value=85.0,
            threshold_value=80.0, message='Test alert for debugging'
        )
        self.assertTrue(self.alert_noise.should_filter(alert))
        alert.message = 'Production critical alert'
        self.assertFalse(self.alert_noise.should_filter(alert))

    def test_alert_noise_filter_alert(self):
        alert = AlertLog.objects.create(
            rule=self.alert_rule, trigger_value=85.0,
            threshold_value=80.0, message='Test alert'
        )
        result = self.alert_noise.filter_alert(alert)
        self.assertIsInstance(result, dict)
        self.assertIn('filtered', result)
        self.assertIn('action', result)
        self.assertIn('reason', result)

    def test_alert_noise_get_target_rules_count(self):
        self.assertEqual(self.alert_noise.get_target_rules_count(), 1)
        alert_rule2 = AlertRule.objects.create(
            name='Memory Alert', alert_type='server_error', severity='low',
            threshold_value=85.0, created_by=self.user
        )
        self.alert_noise.target_rules.add(alert_rule2)
        self.assertEqual(self.alert_noise.get_target_rules_count(), 2)

    def test_alert_noise_get_effectiveness_score(self):
        self.assertEqual(self.alert_noise.get_effectiveness_score(), 0)
        self.alert_noise.total_processed = 100
        self.alert_noise.total_suppressed = 80
        self.alert_noise.save()
        score = self.alert_noise.get_effectiveness_score()
        self.assertEqual(score, 80.0)

    def test_alert_noise_update_statistics(self):
        self.alert_noise.update_statistics(processed=50, suppressed=30, grouped=10, delayed=5)
        self.assertEqual(self.alert_noise.total_processed, 50)
        self.assertEqual(self.alert_noise.total_suppressed, 30)
        self.assertEqual(self.alert_noise.total_grouped, 10)
        self.assertEqual(self.alert_noise.total_delayed, 5)

    def test_alert_noise_reset_statistics(self):
        self.alert_noise.total_processed = 100
        self.alert_noise.total_suppressed = 80
        self.alert_noise.save()
        self.alert_noise.reset_statistics()
        self.assertEqual(self.alert_noise.total_processed, 0)
        self.assertEqual(self.alert_noise.total_suppressed, 0)
        self.assertEqual(self.alert_noise.total_grouped, 0)
        self.assertEqual(self.alert_noise.total_delayed, 0)


class RootCauseAnalysisModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='Database Alert', alert_type='server_error', severity='critical',
            threshold_value=1.0, created_by=self.user
        )
        self.root_cause_analysis = RootCauseAnalysis.objects.create(
            title='Database Connection Failure RCA',
            description='Analysis of database connection failure',
            analysis_method='5_whys',
            confidence_level='high',
            status='completed',
            created_by=self.user
        )
        self.root_cause_analysis.target_alerts.add(self.alert_rule)

    def test_root_cause_analysis_creation(self):
        self.assertEqual(self.root_cause_analysis.title, 'Database Connection Failure RCA')
        self.assertEqual(self.root_cause_analysis.analysis_method, '5_whys')
        self.assertEqual(self.root_cause_analysis.confidence_level, 'high')
        self.assertEqual(self.root_cause_analysis.status, 'completed')
        self.assertEqual(self.root_cause_analysis.created_by, self.user)

    def test_root_cause_analysis_str_representation(self):
        expected = f'RootCauseAnalysis: {self.root_cause_analysis.id} - completed'
        self.assertEqual(str(self.root_cause_analysis), expected)

    def test_root_cause_analysis_get_method_display(self):
        self.assertEqual(self.root_cause_analysis.get_method_display(), '5 Whys')
        self.root_cause_analysis.analysis_method = 'fishbone'
        self.assertEqual(self.root_cause_analysis.get_method_display(), 'Fishbone')
        self.root_cause_analysis.analysis_method = 'statistical'
        self.assertEqual(self.root_cause_analysis.get_method_display(), 'Statistical')

    def test_root_cause_analysis_get_confidence_display(self):
        self.assertEqual(self.root_cause_analysis.get_confidence_display(), 'High')
        self.root_cause_analysis.confidence_level = 'medium'
        self.assertEqual(self.root_cause_analysis.get_confidence_display(), 'Medium')
        self.root_cause_analysis.confidence_level = 'low'
        self.assertEqual(self.root_cause_analysis.get_confidence_display(), 'Low')
        self.root_cause_analysis.confidence_level = 'very_high'
        self.assertEqual(self.root_cause_analysis.get_confidence_display(), 'Very High')

    def test_root_cause_analysis_get_status_display(self):
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'Completed')
        self.root_cause_analysis.status = 'draft'
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'Draft')
        self.root_cause_analysis.status = 'in_progress'
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'In Progress')
        self.root_cause_analysis.status = 'submitted_for_review'
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'Submitted For Review')
        self.root_cause_analysis.status = 'approved'
        self.assertEqual(self.root_cause_analysis.get_status_display(), 'Approved')

    def test_root_cause_analysis_analyze(self):
        for i in range(5):
            alert_log = AlertLog.objects.create(
                rule=self.alert_rule, trigger_value=1.0 + i,
                threshold_value=1.0, message=f'Database error {i}'
            )
            self.root_cause_analysis.related_alerts.add(alert_log)
        result = self.root_cause_analysis.analyze()
        self.assertIsInstance(result, dict)
        self.assertIn('root_causes', result)
        self.assertIn('contributing_factors', result)
        self.assertIn('recommendations', result)

    def test_root_cause_analysis_generate_recommendations(self):
        self.root_cause_analysis.root_causes = [
            {'cause': 'Configuration error', 'confidence': 0.8}
        ]
        self.root_cause_analysis.save()
        self.root_cause_analysis.generate_recommendations()
        self.assertIsInstance(self.root_cause_analysis.immediate_actions, list)
        self.assertIsInstance(self.root_cause_analysis.preventive_actions, list)

    def test_root_cause_analysis_get_target_alerts_count(self):
        self.assertEqual(self.root_cause_analysis.get_target_alerts_count(), 1)
        alert_rule2 = AlertRule.objects.create(
            name='Memory Alert', alert_type='server_error', severity='high',
            threshold_value=1.0, created_by=self.user
        )
        self.root_cause_analysis.target_alerts.add(alert_rule2)
        self.assertEqual(self.root_cause_analysis.get_target_alerts_count(), 2)

    def test_root_cause_analysis_get_analysis_score(self):
        score = self.root_cause_analysis.get_analysis_score()
        self.assertIsInstance(score, (int, float))
        self.assertGreaterEqual(score, 0)
        self.root_cause_analysis.root_causes = [{'cause': 'DB pool exhausted'}]
        self.root_cause_analysis.contributing_factors = [{'factor': 'High load'}]
        self.root_cause_analysis.lessons_learned = 'Need better monitoring'
        self.root_cause_analysis.preventive_measures = 'Increase pool size'
        self.root_cause_analysis.save()
        score = self.root_cause_analysis.get_analysis_score()
        self.assertGreater(score, 0)

    def test_root_cause_analysis_submit_for_review(self):
        reviewer = User.objects.create_user(
            username='reviewer', email='reviewer@example.com', password='testpass123'
        )
        self.root_cause_analysis.submit_for_review(reviewer)
        self.root_cause_analysis.refresh_from_db()
        self.assertEqual(self.root_cause_analysis.status, 'submitted_for_review')
        self.assertEqual(self.root_cause_analysis.reviewed_by, reviewer)
        self.assertIsNotNone(self.root_cause_analysis.reviewed_at)

    def test_root_cause_analysis_approve(self):
        reviewer = User.objects.create_user(
            username='reviewer', email='reviewer@example.com', password='testpass123'
        )
        self.root_cause_analysis.approve(reviewer, 'Analysis is comprehensive')
        self.root_cause_analysis.refresh_from_db()
        self.assertEqual(self.root_cause_analysis.status, 'approved')
        self.assertEqual(self.root_cause_analysis.approved_by, reviewer)
        self.assertEqual(self.root_cause_analysis.approval_note, 'Analysis is comprehensive')
        self.assertIsNotNone(self.root_cause_analysis.approved_at)
