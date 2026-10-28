"""Tests for Threshold Serializers"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from api.alerts.models.threshold import ThresholdConfig, ThresholdBreach, AdaptiveThreshold, ThresholdHistory, ThresholdProfile
from api.alerts.models.core import AlertRule, AlertLog
from api.alerts.serializers.threshold import (
    ThresholdConfigSerializer, ThresholdBreachSerializer, AdaptiveThresholdSerializer,
    ThresholdHistorySerializer, ThresholdProfileSerializer,
    ThresholdConfigListSerializer, ThresholdBreachListSerializer,
    ThresholdBreachAcknowledgeSerializer, ThresholdBreachResolveSerializer,
    ThresholdConfigEvaluateSerializer, AdaptiveThresholdAdaptSerializer,
    ThresholdProfileApplySerializer)
User = get_user_model()


class ThresholdConfigSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.rule = AlertRule.objects.create(
            name='CPU Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, created_by=self.user)
        self.config = ThresholdConfig.objects.create(
            name='CPU Threshold Config', alert_rule=self.rule,
            threshold_type='static', comparison_operator='gt', primary_threshold=80.0)

    def test_serializer_contains_expected_fields(self):
        data = ThresholdConfigSerializer(self.config).data
        for f in ['id', 'threshold_type', 'comparison_operator', 'primary_threshold', 'is_active', 'created_at']:
            self.assertIn(f, data)

    def test_serializer_valid_data_creates_object(self):
        s = ThresholdConfigSerializer(data={
            'name': 'New Config', 'alert_rule': self.rule.id,
            'threshold_type': 'static', 'comparison_operator': 'gt', 'primary_threshold': 75.0})
        self.assertTrue(s.is_valid(), s.errors)

    def test_serializer_missing_required_fields(self):
        s = ThresholdConfigSerializer(data={'name': 'Incomplete'})
        self.assertFalse(s.is_valid())
        self.assertIn('primary_threshold', s.errors)

    def test_list_serializer_returns_summary(self):
        data = ThresholdConfigListSerializer(self.config).data
        for f in ['id', 'threshold_type', 'primary_threshold', 'is_active', 'created_at']:
            self.assertIn(f, data)


class ThresholdBreachSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('breachuser', 'breach@example.com', 'testpass123')
        self.rule = AlertRule.objects.create(
            name='Breach Rule', alert_type='server_error', severity='critical',
            threshold_value=90.0, created_by=self.user)
        self.config = ThresholdConfig.objects.create(
            name='Breach Config', alert_rule=self.rule,
            threshold_type='static', comparison_operator='gt', primary_threshold=90.0)
        self.alert_log = AlertLog.objects.create(
            rule=self.rule, trigger_value=95.0, threshold_value=90.0, message='Breach')
        self.breach = ThresholdBreach.objects.create(
            threshold_config=self.config, alert_log=self.alert_log,
            breach_value=95.0, threshold_value=90.0, severity='critical',
            breach_percentage=5.56)

    def test_serializer_read(self):
        data = ThresholdBreachSerializer(self.breach).data
        for f in ['id', 'breach_value', 'threshold_value', 'severity', 'is_resolved']:
            self.assertIn(f, data)

    def test_breach_acknowledge_serializer_valid(self):
        s = ThresholdBreachAcknowledgeSerializer(data={'notes': 'Acknowledged'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_breach_resolve_serializer_valid(self):
        s = ThresholdBreachResolveSerializer(data={'notes': 'Fixed by scaling'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_breach_list_serializer(self):
        data = ThresholdBreachListSerializer(self.breach).data
        for f in ['id', 'severity', 'is_resolved', 'breach_value']:
            self.assertIn(f, data)


class AdaptiveThresholdSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('user2', 'user2@example.com', 'testpass123')
        self.rule = AlertRule.objects.create(
            name='Adaptive Rule', alert_type='server_error', severity='medium',
            threshold_value=70.0, created_by=self.user)
        self.config = ThresholdConfig.objects.create(
            name='Adaptive Config', alert_rule=self.rule,
            threshold_type='dynamic', comparison_operator='gt', primary_threshold=70.0)
        self.adaptive = AdaptiveThreshold.objects.create(
            name='CPU Adaptive', threshold_config=self.config,
            adaptation_method='exponential_smoothing',
            base_threshold=70.0, min_threshold=60.0,
            max_threshold=90.0, current_threshold=70.0)

    def test_serializer_read(self):
        data = AdaptiveThresholdSerializer(self.adaptive).data
        for f in ['id', 'name', 'adaptation_method', 'current_threshold', 'is_active']:
            self.assertIn(f, data)

    def test_adapt_serializer_valid(self):
        s = AdaptiveThresholdAdaptSerializer(data={'reason': 'Manual adjustment'})
        self.assertTrue(s.is_valid(), s.errors)


class ThresholdProfileSerializerTest(TestCase):
    def setUp(self):
        self.profile = ThresholdProfile.objects.create(
            name='Production Profile', description='Production thresholds',
            profile_type='balanced', sensitivity_level=0.5, is_active=True)

    def test_serializer_read(self):
        data = ThresholdProfileSerializer(self.profile).data
        for f in ['id', 'name', 'profile_type', 'is_active', 'description']:
            self.assertIn(f, data)

    def test_apply_serializer_valid(self):
        user = User.objects.create_user('u3', 'u3@e.com', 'pass')
        rule = AlertRule.objects.create(
            name='R2', alert_type='server_error', severity='high',
            threshold_value=80.0, created_by=user)
        config = ThresholdConfig.objects.create(
            name='C2', alert_rule=rule, threshold_type='static',
            comparison_operator='gt', primary_threshold=80.0)
        s = ThresholdProfileApplySerializer(data={'threshold_config_id': config.id})
        self.assertTrue(s.is_valid(), s.errors)


class ThresholdConfigEvaluateSerializerTest(TestCase):
    def test_evaluate_serializer_valid(self):
        s = ThresholdConfigEvaluateSerializer(data={'current_value': 85.0})
        self.assertTrue(s.is_valid(), s.errors)

    def test_evaluate_serializer_missing_value(self):
        s = ThresholdConfigEvaluateSerializer(data={})
        self.assertFalse(s.is_valid())
        self.assertIn('current_value', s.errors)
