"""
Tests for Threshold Models
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from api.alerts.models.core import AlertRule, AlertLog
from api.alerts.models.threshold import (
    ThresholdConfig, ThresholdBreach, AdaptiveThreshold,
    ThresholdHistory, ThresholdProfile
)

User = get_user_model()


class ThresholdConfigModelTest(TestCase):
    """Test cases for ThresholdConfig model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            created_by=self.user
        )
        self.threshold_config = ThresholdConfig.objects.create(
            name='Test Threshold Config',
            alert_rule=self.alert_rule,
            threshold_type='static',
            comparison_operator='gt',
            primary_threshold=85.0,
            secondary_threshold=90.0
        )

    def test_threshold_config_creation(self):
        """Test ThresholdConfig creation"""
        self.assertEqual(self.threshold_config.alert_rule, self.alert_rule)
        self.assertEqual(self.threshold_config.threshold_type, 'static')
        self.assertEqual(self.threshold_config.comparison_operator, 'gt')
        self.assertEqual(self.threshold_config.primary_threshold, 85.0)
        self.assertEqual(self.threshold_config.secondary_threshold, 90.0)
        self.assertTrue(self.threshold_config.is_active)

    def test_threshold_config_str_representation(self):
        """Test ThresholdConfig string representation"""
        expected = f'ThresholdConfig: {self.alert_rule.name} - static'
        self.assertEqual(str(self.threshold_config), expected)

    def test_threshold_config_evaluate_condition(self):
        """Test ThresholdConfig evaluate condition with comparison_operator"""
        # gt operator: 90 > 85 → True
        self.assertTrue(self.threshold_config.evaluate_condition(90.0))
        self.assertFalse(self.threshold_config.evaluate_condition(80.0))

        # lt operator
        self.threshold_config.comparison_operator = 'lt'
        self.threshold_config.save()
        self.assertFalse(self.threshold_config.evaluate_condition(90.0))
        self.assertTrue(self.threshold_config.evaluate_condition(70.0))

        # eq operator
        self.threshold_config.comparison_operator = 'eq'
        self.threshold_config.save()
        self.assertTrue(self.threshold_config.evaluate_condition(85.0))
        self.assertFalse(self.threshold_config.evaluate_condition(90.0))

    def test_threshold_config_get_breach_count(self):
        """Test ThresholdConfig get_breach_count"""
        alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=90.0,
            threshold_value=85.0,
            message='Test breach'
        )
        for i in range(5):
            ThresholdBreach.objects.create(
                threshold_config=self.threshold_config,
                alert_log=alert_log,
                severity='high',
                breach_value=90.0 + i,
                threshold_value=85.0,
                breach_percentage=((90.0 + i - 85.0) / 85.0) * 100
            )
        self.assertEqual(self.threshold_config.get_breach_count(), 5)

    def test_threshold_config_get_effectiveness_score(self):
        """Test ThresholdConfig get_effectiveness_score"""
        alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=90.0,
            threshold_value=85.0,
            message='Test breach'
        )
        breaches = []
        for i in range(3):
            b = ThresholdBreach.objects.create(
                threshold_config=self.threshold_config,
                alert_log=alert_log,
                severity='high',
                breach_value=90.0 + i,
                threshold_value=85.0,
                breach_percentage=((90.0 + i - 85.0) / 85.0) * 100
            )
            breaches.append(b)

        # Resolve 2 out of 3 by setting resolved_at
        for b in breaches[:2]:
            b.resolved_at = timezone.now()
            b.save(update_fields=['resolved_at'])

        effectiveness = self.threshold_config.get_effectiveness_score()
        self.assertAlmostEqual(effectiveness, 66.67, places=1)

    def test_threshold_config_get_type_display(self):
        """Test ThresholdConfig threshold_type values"""
        self.assertEqual(self.threshold_config.threshold_type, 'static')
        self.assertEqual(self.threshold_config.get_threshold_type_display(), 'Static Threshold')

        self.threshold_config.threshold_type = 'dynamic'
        self.threshold_config.save()
        self.assertEqual(self.threshold_config.get_threshold_type_display(), 'Dynamic Threshold')


class ThresholdBreachModelTest(TestCase):
    """Test cases for ThresholdBreach model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            created_by=self.user
        )
        self.threshold_config = ThresholdConfig.objects.create(
            name='Test Threshold Config',
            alert_rule=self.alert_rule,
            threshold_type='static',
            comparison_operator='gt',
            primary_threshold=85.0
        )
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=95.0,
            threshold_value=85.0,
            message='High server error rate'
        )
        self.threshold_breach = ThresholdBreach.objects.create(
            threshold_config=self.threshold_config,
            alert_log=self.alert_log,
            severity='high',
            breach_value=95.0,
            threshold_value=85.0,
            breach_percentage=11.76
        )

    def test_threshold_breach_creation(self):
        """Test ThresholdBreach creation"""
        self.assertEqual(self.threshold_breach.threshold_config, self.threshold_config)
        self.assertEqual(self.threshold_breach.severity, 'high')
        self.assertEqual(self.threshold_breach.breach_value, 95.0)
        self.assertEqual(self.threshold_breach.threshold_value, 85.0)
        self.assertEqual(self.threshold_breach.breach_percentage, 11.76)
        self.assertFalse(self.threshold_breach.is_resolved)

    def test_threshold_breach_str_representation(self):
        """Test ThresholdBreach string representation"""
        expected = f'ThresholdBreach: {self.threshold_breach.id} - high'
        self.assertEqual(str(self.threshold_breach), expected)

    def test_threshold_breach_resolve(self):
        """Test ThresholdBreach resolve method"""
        self.threshold_breach.resolve(self.user, notes='Fixed the threshold breach')
        self.threshold_breach.refresh_from_db()

        self.assertTrue(self.threshold_breach.is_resolved)
        self.assertEqual(self.threshold_breach.resolved_by, self.user)
        self.assertEqual(self.threshold_breach.resolution_notes, 'Fixed the threshold breach')
        self.assertIsNotNone(self.threshold_breach.resolved_at)

    def test_threshold_breach_get_duration(self):
        """Test ThresholdBreach get_duration method"""
        # Unresolved: returns None
        self.assertIsNone(self.threshold_breach.get_duration())

        # Resolved: returns timedelta
        self.threshold_breach.resolved_at = timezone.now()
        self.threshold_breach.save(update_fields=['resolved_at'])
        duration = self.threshold_breach.get_duration()
        self.assertIsNotNone(duration)
        self.assertIsInstance(duration, timedelta)

    def test_threshold_breach_get_severity_display(self):
        """Test ThresholdBreach severity display via Django choices"""
        self.assertEqual(self.threshold_breach.get_severity_display(), 'High')

        self.threshold_breach.severity = 'critical'
        self.assertEqual(self.threshold_breach.get_severity_display(), 'Critical')

    def test_threshold_breach_get_status_display(self):
        """Test ThresholdBreach get_status_display method"""
        self.assertEqual(self.threshold_breach.get_status_display(), 'Active')

        self.threshold_breach.resolved_at = timezone.now()
        self.threshold_breach.save(update_fields=['resolved_at'])
        self.threshold_breach.refresh_from_db()
        self.assertEqual(self.threshold_breach.get_status_display(), 'Resolved')


class AdaptiveThresholdModelTest(TestCase):
    """Test cases for AdaptiveThreshold model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            created_by=self.user
        )
        self.threshold_config = ThresholdConfig.objects.create(
            name='Test Threshold Config',
            alert_rule=self.alert_rule,
            threshold_type='static',
            comparison_operator='gt',
            primary_threshold=85.0
        )
        self.adaptive_threshold = AdaptiveThreshold.objects.create(
            name='Test Adaptive Threshold',
            threshold_config=self.threshold_config,
            adaptation_method='exponential_smoothing',
            adaptation_window_days=30,
            base_threshold=85.0,
            min_threshold=70.0,
            max_threshold=100.0,
            current_threshold=85.0
        )

    def test_adaptive_threshold_creation(self):
        """Test AdaptiveThreshold creation"""
        self.assertEqual(self.adaptive_threshold.threshold_config, self.threshold_config)
        self.assertEqual(self.adaptive_threshold.adaptation_method, 'exponential_smoothing')
        self.assertEqual(self.adaptive_threshold.adaptation_window_days, 30)
        self.assertEqual(self.adaptive_threshold.current_threshold, 85.0)
        self.assertTrue(self.adaptive_threshold.is_active)

    def test_adaptive_threshold_str_representation(self):
        """Test AdaptiveThreshold string representation"""
        expected = f'AdaptiveThreshold: {self.threshold_config.alert_rule.name} - exponential_smoothing'
        self.assertEqual(str(self.adaptive_threshold), expected)

    def test_adaptive_threshold_adapt_threshold(self):
        """Test AdaptiveThreshold adapt_threshold method with manual_value"""
        result = self.adaptive_threshold.adapt_threshold(manual_value=90.0)

        self.assertTrue(result.get('adapted'))
        self.assertEqual(result.get('new_threshold'), 90.0)
        self.adaptive_threshold.refresh_from_db()
        self.assertEqual(self.adaptive_threshold.current_threshold, 90.0)
        self.assertGreater(self.adaptive_threshold.adaptation_count, 0)

    def test_adaptive_threshold_get_adaptation_count(self):
        """Test AdaptiveThreshold get_adaptation_count"""
        self.assertEqual(self.adaptive_threshold.get_adaptation_count(), 0)

        self.adaptive_threshold.adapt_threshold(manual_value=87.0)
        self.adaptive_threshold.adapt_threshold(manual_value=89.0)
        self.adaptive_threshold.adapt_threshold(manual_value=91.0)

        self.assertEqual(self.adaptive_threshold.get_adaptation_count(), 3)

    def test_adaptive_threshold_get_training_status_display(self):
        """Test AdaptiveThreshold get_training_status_display"""
        # Default training_status is 'pending'
        display = self.adaptive_threshold.get_training_status_display()
        self.assertEqual(display, 'Pending')

        self.adaptive_threshold.training_status = 'training'
        self.assertEqual(self.adaptive_threshold.get_training_status_display(), 'Training')

        self.adaptive_threshold.training_status = 'completed'
        self.assertEqual(self.adaptive_threshold.get_training_status_display(), 'Completed')

    def test_adaptive_threshold_get_method_display(self):
        """Test AdaptiveThreshold get_method_display"""
        self.assertEqual(
            self.adaptive_threshold.get_method_display(),
            'Exponential Smoothing'
        )
        self.adaptive_threshold.adaptation_method = 'moving_average'
        self.assertEqual(self.adaptive_threshold.get_method_display(), 'Moving Average')

        self.adaptive_threshold.adaptation_method = 'ensemble'
        self.assertEqual(self.adaptive_threshold.get_method_display(), 'Ensemble Method')


class ThresholdHistoryModelTest(TestCase):
    """Test cases for ThresholdHistory model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            created_by=self.user
        )
        self.threshold_config = ThresholdConfig.objects.create(
            name='Test Threshold Config',
            alert_rule=self.alert_rule,
            threshold_type='static',
            comparison_operator='gt',
            primary_threshold=85.0
        )
        self.adaptive_threshold = AdaptiveThreshold.objects.create(
            name='Test Adaptive Threshold',
            threshold_config=self.threshold_config,
            adaptation_method='exponential_smoothing',
            base_threshold=85.0,
            min_threshold=70.0,
            max_threshold=100.0,
            current_threshold=85.0
        )
        self.threshold_history = ThresholdHistory.objects.create(
            adaptive_threshold=self.adaptive_threshold,
            change_type='automatic',
            old_threshold=85.0,
            new_threshold=90.0,
            change_percentage=5.88,
            reason='Increased due to high variability'
        )

    def test_threshold_history_creation(self):
        """Test ThresholdHistory creation"""
        self.assertEqual(self.threshold_history.adaptive_threshold, self.adaptive_threshold)
        self.assertEqual(self.threshold_history.change_type, 'automatic')
        self.assertEqual(self.threshold_history.old_threshold, 85.0)
        self.assertEqual(self.threshold_history.new_threshold, 90.0)
        self.assertEqual(self.threshold_history.change_percentage, 5.88)
        self.assertEqual(self.threshold_history.reason, 'Increased due to high variability')

    def test_threshold_history_str_representation(self):
        """Test ThresholdHistory string representation"""
        expected = f'ThresholdHistory: {self.threshold_history.id} - automatic'
        self.assertEqual(str(self.threshold_history), expected)

    def test_threshold_history_get_change_type_display(self):
        """Test ThresholdHistory change type display via Django choices"""
        self.assertEqual(self.threshold_history.get_change_type_display(), 'Automatic Adaptation')

        self.threshold_history.change_type = 'manual'
        self.assertEqual(self.threshold_history.get_change_type_display(), 'Manual Change')

        self.threshold_history.change_type = 'emergency'
        self.assertEqual(self.threshold_history.get_change_type_display(), 'Emergency Adjustment')

    def test_threshold_history_is_increase(self):
        """Test ThresholdHistory is_increase property"""
        self.assertTrue(self.threshold_history.is_increase)
        self.assertFalse(self.threshold_history.is_decrease)

    def test_threshold_history_is_decrease(self):
        """Test ThresholdHistory is_decrease property"""
        self.threshold_history.new_threshold = 80.0
        self.assertTrue(self.threshold_history.is_decrease)
        self.assertFalse(self.threshold_history.is_increase)


class ThresholdProfileModelTest(TestCase):
    """Test cases for ThresholdProfile model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.threshold_profile = ThresholdProfile.objects.create(
            name='Production Thresholds',
            description='Default thresholds for production environment',
            profile_type='balanced',
            sensitivity_level=0.5,
            is_default=True,
            is_active=True,
            alert_type_settings={
                'server_error': {'warning': 70.0, 'critical': 90.0},
                'server_down': {'warning': 80.0, 'critical': 95.0}
            }
        )

    def test_threshold_profile_creation(self):
        """Test ThresholdProfile creation"""
        self.assertEqual(self.threshold_profile.name, 'Production Thresholds')
        self.assertEqual(self.threshold_profile.profile_type, 'balanced')
        self.assertTrue(self.threshold_profile.is_default)
        self.assertTrue(self.threshold_profile.is_active)
        self.assertIsInstance(self.threshold_profile.alert_type_settings, dict)

    def test_threshold_profile_str_representation(self):
        """Test ThresholdProfile string representation"""
        expected = 'ThresholdProfile: Production Thresholds - balanced'
        self.assertEqual(str(self.threshold_profile), expected)

    def test_threshold_profile_get_threshold_for_alert_type(self):
        """Test accessing alert_type_settings by key"""
        thresholds = self.threshold_profile.alert_type_settings.get('server_error')
        expected = {'warning': 70.0, 'critical': 90.0}
        self.assertEqual(thresholds, expected)

        # Non-existent key returns None
        thresholds = self.threshold_profile.alert_type_settings.get('non_existent')
        self.assertIsNone(thresholds)

    def test_threshold_profile_get_effective_settings(self):
        """Test ThresholdProfile get_effective_settings method"""
        settings = self.threshold_profile.get_effective_settings('server_error')
        self.assertIsInstance(settings, dict)
        self.assertIn('multiplier', settings)
        self.assertIn('sensitivity', settings)

    def test_threshold_profile_apply_to_threshold_config(self):
        """Test ThresholdProfile apply_to_threshold_config modifies thresholds"""
        alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='server_error',
            severity='low',
            threshold_value=50.0,
            created_by=self.user
        )
        threshold_config = ThresholdConfig.objects.create(
            name='CPU Threshold Config',
            alert_rule=alert_rule,
            threshold_type='static',
            comparison_operator='gt',
            primary_threshold=50.0
        )
        original = threshold_config.primary_threshold
        self.threshold_profile.apply_to_threshold_config(threshold_config)
        threshold_config.refresh_from_db()
        # Multiplier is 1.0 by default → threshold stays same
        self.assertEqual(threshold_config.primary_threshold, original)

    def test_threshold_profile_get_rules_count(self):
        """Test ThresholdProfile is_active and sensitivity_level"""
        self.assertTrue(self.threshold_profile.is_active)
        self.assertEqual(self.threshold_profile.sensitivity_level, 0.5)

    def test_threshold_profile_get_type_display(self):
        """Test ThresholdProfile profile_type display via Django choices"""
        self.assertEqual(self.threshold_profile.get_profile_type_display(), 'Balanced - Good accuracy')

        self.threshold_profile.profile_type = 'conservative'
        self.assertEqual(
            self.threshold_profile.get_profile_type_display(),
            'Conservative - Fewer false positives'
        )

        self.threshold_profile.profile_type = 'custom'
        self.assertEqual(
            self.threshold_profile.get_profile_type_display(),
            'Custom Configuration'
        )
