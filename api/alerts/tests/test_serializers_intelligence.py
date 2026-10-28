"""Tests for Intelligence Serializers"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from api.alerts.models.core import AlertRule
from api.alerts.models.intelligence import AlertCorrelation, AlertPrediction, AnomalyDetectionModel, AlertNoise, RootCauseAnalysis
from api.alerts.serializers.intelligence import (
    AlertCorrelationSerializer, AlertPredictionSerializer, AnomalyDetectionModelSerializer,
    AlertNoiseSerializer, RootCauseAnalysisSerializer, AlertCorrelationListSerializer,
    AlertPredictionListSerializer, RootCauseAnalysisListSerializer)
User = get_user_model()


class AlertCorrelationSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.rule1 = AlertRule.objects.create(name='R1', alert_type='server_error', severity='high', threshold_value=80.0, created_by=self.user)
        self.rule2 = AlertRule.objects.create(name='R2', alert_type='server_error', severity='high', threshold_value=85.0, created_by=self.user)
        self.correlation = AlertCorrelation.objects.create(
            name='CPU-Memory Correlation', correlation_type='temporal',
            status='confirmed', correlation_coefficient=0.85, p_value=0.001,
            confidence_level=0.9, correlation_strength=0.85,
            time_window_minutes=15, correlation_threshold=0.8,
            minimum_occurrences=3, model_type='linear', model_parameters={})
        self.correlation.primary_rules.add(self.rule1, self.rule2)

    def test_serializer_read(self):
        data = AlertCorrelationSerializer(self.correlation).data
        for f in ['id', 'name', 'correlation_type', 'status', 'correlation_coefficient',
                  'confidence_level', 'primary_rules_count', 'secondary_rules_count']:
            self.assertIn(f, data)

    def test_list_serializer(self):
        data = AlertCorrelationListSerializer(self.correlation).data
        for f in ['id', 'name', 'correlation_type', 'status', 'correlation_strength']:
            self.assertIn(f, data)

    def test_serializer_create(self):
        s = AlertCorrelationSerializer(data={
            'name': 'New Correlation', 'correlation_type': 'causal',
            'status': 'pending', 'correlation_threshold': 0.7,
            'minimum_occurrences': 3, 'time_window_minutes': 30,
            'model_type': 'linear', 'model_parameters': {}
        })
        self.assertTrue(s.is_valid(), s.errors)


class AlertPredictionSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.rule = AlertRule.objects.create(name='R1', alert_type='server_error', severity='high', threshold_value=80.0, created_by=self.user)
        self.prediction = AlertPrediction.objects.create(
            name='CPU Prediction', prediction_type='threshold_breach',
            model_type='linear_regression', training_status='completed',
            training_days=30, prediction_horizon_hours=24,
            model_parameters={}, feature_columns=['cpu', 'memory'])
        self.prediction.target_rules.add(self.rule)

    def test_serializer_read(self):
        data = AlertPredictionSerializer(self.prediction).data
        for f in ['id', 'name', 'prediction_type', 'model_type', 'training_status',
                  'target_rules_count']:
            self.assertIn(f, data)

    def test_list_serializer(self):
        data = AlertPredictionListSerializer(self.prediction).data
        for f in ['id', 'name', 'prediction_type', 'model_type', 'training_status']:
            self.assertIn(f, data)


class AnomalyDetectionModelSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.rule = AlertRule.objects.create(name='R1', alert_type='server_error', severity='high', threshold_value=80.0, created_by=self.user)
        self.model = AnomalyDetectionModel.objects.create(
            name='CPU Anomaly', detection_method='statistical',
            sensitivity=0.8, window_size_minutes=60, baseline_days=7,
            anomaly_threshold=2.0, min_alert_count=3, model_parameters={})
        self.model.target_rules.add(self.rule)

    def test_serializer_read(self):
        data = AnomalyDetectionModelSerializer(self.model).data
        for f in ['id', 'name', 'detection_method', 'is_active', 'target_rules_count']:
            self.assertIn(f, data)


class AlertNoiseSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.rule = AlertRule.objects.create(name='R1', alert_type='server_error', severity='low', threshold_value=80.0, created_by=self.user)
        self.noise = AlertNoise.objects.create(
            name='Debug Filter', noise_type='suppression', action='suppress',
            message_patterns=['test', 'debug'], severity_filter=['low'],
            source_filter=[], suppression_duration_minutes=60,
            max_suppressions_per_hour=10, group_window_minutes=15, max_group_size=5)
        self.noise.target_rules.add(self.rule)

    def test_serializer_read(self):
        data = AlertNoiseSerializer(self.noise).data
        for f in ['id', 'name', 'noise_type', 'action', 'is_active',
                  'target_rules_count', 'effectiveness_score']:
            self.assertIn(f, data)


class RootCauseAnalysisSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.rca = RootCauseAnalysis.objects.create(
            title='DB Connection Failure RCA', description='Analysis',
            analysis_method='5_whys', confidence_level='high',
            status='completed', created_by=self.user)

    def test_serializer_read(self):
        data = RootCauseAnalysisSerializer(self.rca).data
        for f in ['id', 'title', 'analysis_method', 'confidence_level',
                  'status', 'analysis_score']:
            self.assertIn(f, data)

    def test_list_serializer(self):
        data = RootCauseAnalysisListSerializer(self.rca).data
        for f in ['id', 'title', 'analysis_method', 'status', 'created_at']:
            self.assertIn(f, data)
