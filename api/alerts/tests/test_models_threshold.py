"""
Tests for Threshold Models
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog
from alerts.models.threshold import (
    ThresholdConfig, ThresholdBreach, AdaptiveThreshold, 
    ThresholdHistory, ThresholdProfile
)


class ThresholdConfigModelTest(TestCase):
    """Test cases for ThresholdConfig model"""
    
    def setUp(self):
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=15
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
    
    def test_threshold_config_creation(self):
        """Test ThresholdConfig creation"""
        self.assertEqual(self.threshold_config.alert_rule, self.alert_rule)
        self.assertEqual(self.threshold_config.threshold_type, 'absolute')
        self.assertEqual(self.threshold_config.operator, 'greater_than')
        self.assertEqual(self.threshold_config.primary_threshold, 85.0)
        self.assertEqual(self.threshold_config.secondary_threshold, 90.0)
        self.assertTrue(self.threshold_config.is_active)
    
    def test_threshold_config_str_representation(self):
        """Test ThresholdConfig string representation"""
        expected = f'ThresholdConfig: {self.alert_rule.name} - absolute'
        self.assertEqual(str(self.threshold_config), expected)
    
    def test_threshold_config_evaluate_condition(self):
        """Test ThresholdConfig evaluate condition method"""
        # Test greater_than operator
        self.assertTrue(self.threshold_config.evaluate_condition(90.0))
        self.assertFalse(self.threshold_config.evaluate_condition(80.0))
        
        # Test less_than operator
        self.threshold_config.operator = 'less_than'
        self.threshold_config.save()
        self.assertFalse(self.threshold_config.evaluate_condition(90.0))
        self.assertTrue(self.threshold_config.evaluate_condition(70.0))
        
        # Test equal_to operator
        self.threshold_config.operator = 'equal_to'
        self.threshold_config.save()
        self.assertTrue(self.threshold_config.evaluate_condition(85.0))
        self.assertFalse(self.threshold_config.evaluate_condition(90.0))
    
    def test_threshold_config_get_breach_count(self):
        """Test ThresholdConfig get breach count"""
        # Create some breaches
        for i in range(5):
            ThresholdBreach.objects.create(
                threshold_config=self.threshold_config,
                severity='high',
                breach_value=90.0 + i,
                threshold_value=85.0,
                breach_percentage=((90.0 + i - 85.0) / 85.0) * 100
            )
        
        breach_count = self.threshold_config.get_breach_count()
        self.assertEqual(breach_count, 5)
    
    def test_threshold_config_get_effectiveness_score(self):
        """Test ThresholdConfig effectiveness score"""
        # Create some breaches
        for i in range(3):
            breach = ThresholdBreach.objects.create(
                threshold_config=self.threshold_config,
                severity='high',
                breach_value=90.0 + i,
                threshold_value=85.0,
                breach_percentage=((90.0 + i - 85.0) / 85.0) * 100
            )
            # Resolve 2 out of 3 breaches
            if i < 2:
                breach.is_resolved = True
                breach.save()
        
        effectiveness = self.threshold_config.get_effectiveness_score()
        expected = (2 / 3) * 100  # 66.67%
        self.assertAlmostEqual(effectiveness, expected, places=2)
    
    def test_threshold_config_get_type_display(self):
        """Test ThresholdConfig type display"""
        self.assertEqual(self.threshold_config.get_type_display(), 'Absolute')
        
        self.threshold_config.threshold_type = 'adaptive'
        self.assertEqual(self.threshold_config.get_type_display(), 'Adaptive')
        
        self.threshold_config.threshold_type = 'percentage'
        self.assertEqual(self.threshold_config.get_type_display(), 'Percentage')


class ThresholdBreachModelTest(TestCase):
    """Test cases for ThresholdBreach model"""
    
    def setUp(self):
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=15
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
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.threshold_breach.resolve(user, 'Fixed the threshold breach')
        
        self.assertTrue(self.threshold_breach.is_resolved)
        self.assertEqual(self.threshold_breach.resolved_by, user)
        self.assertEqual(self.threshold_breach.resolution_note, 'Fixed the threshold breach')
        self.assertIsNotNone(self.threshold_breach.resolved_at)
    
    def test_threshold_breck_get_duration(self):
        """Test ThresholdBreach duration calculation"""
        # Test unresolved breach
        self.assertIsNone(self.threshold_breach.get_duration())
        
        # Test resolved breach
        self.threshold_breach.detected_at = timezone.now() - timedelta(minutes=30)
        self.threshold_breach.resolved_at = timezone.now() - timedelta(minutes=10)
        self.threshold_breach.save()
        
        duration = self.threshold_breach.get_duration()
        self.assertEqual(duration, timedelta(minutes=20))
    
    def test_threshold_breach_get_severity_display(self):
        """Test ThresholdBreach severity display"""
        self.assertEqual(self.threshold_breach.get_severity_display(), 'High')
        
        self.threshold_breach.severity = 'critical'
        self.assertEqual(self.threshold_breach.get_severity_display(), 'Critical')
    
    def test_threshold_breach_get_status_display(self):
        """Test ThresholdBreach status display"""
        self.assertEqual(self.threshold_breach.get_status_display(), 'Active')
        
        self.threshold_breach.is_resolved = True
        self.assertEqual(self.threshold_breach.get_status_display(), 'Resolved')


class AdaptiveThresholdModelTest(TestCase):
    """Test cases for AdaptiveThreshold model"""
    
    def setUp(self):
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=15
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
    
    def test_adaptive_threshold_creation(self):
        """Test AdaptiveThreshold creation"""
        self.assertEqual(self.adaptive_threshold.threshold_config, self.threshold_config)
        self.assertEqual(self.adaptive_threshold.adaptation_method, 'statistical')
        self.assertEqual(self.adaptive_threshold.learning_period_days, 30)
        self.assertEqual(self.adaptive_threshold.confidence_threshold, 0.9)
        self.assertTrue(self.adaptive_threshold.is_active)
    
    def test_adaptive_threshold_str_representation(self):
        """Test AdaptiveThreshold string representation"""
        expected = f'AdaptiveThreshold: {self.threshold_config.alert_rule.name} - statistical'
        self.assertEqual(str(self.adaptive_threshold), expected)
    
    def test_adaptive_threshold_adapt_threshold(self):
        """Test AdaptiveThreshold adapt threshold method"""
        new_threshold = 90.0
        reason = 'Increased due to high variability'
        
        self.adaptive_threshold.adapt_threshold(new_threshold, reason)
        
        self.assertEqual(self.adaptive_threshold.current_threshold, new_threshold)
        self.assertIsNotNone(self.adaptive_threshold.last_adaptation)
        
        # Check if history was created
        history = ThresholdHistory.objects.filter(
            adaptive_threshold=self.adaptive_threshold
        ).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.new_threshold, new_threshold)
        self.assertEqual(history.reason, reason)
    
    def test_adaptive_threshold_get_adaptation_count(self):
        """Test AdaptiveThreshold get adaptation count"""
        # Initially should be 0
        self.assertEqual(self.adaptive_threshold.get_adaptation_count(), 0)
        
        # Add some adaptations
        for i in range(3):
            ThresholdHistory.objects.create(
                adaptive_threshold=self.adaptive_threshold,
                change_type='adaptation',
                old_threshold=85.0 + i,
                new_threshold=85.0 + i + 1,
                reason=f'Test adaptation {i}'
            )
        
        self.assertEqual(self.adaptive_threshold.get_adaptation_count(), 3)
    
    def test_adaptive_threshold_get_training_status_display(self):
        """Test AdaptiveThreshold training status display"""
        self.assertEqual(self.adaptive_threshold.get_training_status_display(), 'Pending')
        
        self.adaptive_threshold.training_status = 'training'
        self.assertEqual(self.adaptive_threshold.get_training_status_display(), 'Training')
        
        self.adaptive_threshold.training_status = 'completed'
        self.assertEqual(self.adaptive_threshold.get_training_status_display(), 'Completed')
    
    def test_adaptive_threshold_get_method_display(self):
        """Test AdaptiveThreshold method display"""
        self.assertEqual(self.adaptive_threshold.get_method_display(), 'Statistical')
        
        self.adaptive_threshold.adaptation_method = 'machine_learning'
        self.assertEqual(self.adaptive_threshold.get_method_display(), 'Machine Learning')
        
        self.adaptive_threshold.adaptation_method = 'hybrid'
        self.assertEqual(self.adaptive_threshold.get_method_display(), 'Hybrid')


class ThresholdHistoryModelTest(TestCase):
    """Test cases for ThresholdHistory model"""
    
    def setUp(self):
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=15
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
    
    def test_threshold_history_creation(self):
        """Test ThresholdHistory creation"""
        self.assertEqual(self.threshold_history.adaptive_threshold, self.adaptive_threshold)
        self.assertEqual(self.threshold_history.change_type, 'adaptation')
        self.assertEqual(self.threshold_history.old_threshold, 85.0)
        self.assertEqual(self.threshold_history.new_threshold, 90.0)
        self.assertEqual(self.threshold_history.change_percentage, 5.88)
        self.assertEqual(self.threshold_history.reason, 'Increased due to high variability')
    
    def test_threshold_history_str_representation(self):
        """Test ThresholdHistory string representation"""
        expected = f'ThresholdHistory: {self.threshold_history.id} - adaptation'
        self.assertEqual(str(self.threshold_history), expected)
    
    def test_threshold_history_get_change_type_display(self):
        """Test ThresholdHistory change type display"""
        self.assertEqual(self.threshold_history.get_change_type_display(), 'Adaptation')
        
        self.threshold_history.change_type = 'manual'
        self.assertEqual(self.threshold_history.get_change_type_display(), 'Manual')
        
        self.threshold_history.change_type = 'reset'
        self.assertEqual(self.threshold_history.get_change_type_display(), 'Reset')


class ThresholdProfileModelTest(TestCase):
    """Test cases for ThresholdProfile model"""
    
    def setUp(self):
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
    
    def test_threshold_profile_creation(self):
        """Test ThresholdProfile creation"""
        self.assertEqual(self.threshold_profile.name, 'Production Thresholds')
        self.assertEqual(self.threshold_profile.profile_type, 'environment')
        self.assertTrue(self.threshold_profile.is_default)
        self.assertTrue(self.threshold_profile.is_active)
        self.assertIsInstance(self.threshold_profile.threshold_settings, dict)
        self.assertIsInstance(self.threshold_profile.alert_type_mappings, dict)
    
    def test_threshold_profile_str_representation(self):
        """Test ThresholdProfile string representation"""
        expected = f'ThresholdProfile: {self.threshold_profile.name} - environment'
        self.assertEqual(str(self.threshold_profile), expected)
    
    def test_threshold_profile_get_threshold_for_alert_type(self):
        """Test ThresholdProfile get threshold for alert type"""
        thresholds = self.threshold_profile.get_threshold_for_alert_type('cpu_usage')
        expected = {'warning': 70.0, 'critical': 90.0}
        self.assertEqual(thresholds, expected)
        
        # Test non-existent alert type
        thresholds = self.threshold_profile.get_threshold_for_alert_type('non_existent')
        self.assertEqual(thresholds, {})
    
    def test_threshold_profile_get_severity_for_alert_type(self):
        """Test ThresholdProfile get severity for alert type"""
        severity = self.threshold_profile.get_severity_for_alert_type('cpu_usage')
        self.assertEqual(severity, 'high')
        
        # Test non-existent alert type
        severity = self.threshold_profile.get_severity_for_alert_type('non_existent')
        self.assertIsNone(severity)
    
    def test_threshold_profile_apply_to_rule(self):
        """Test ThresholdProfile apply to rule method"""
        alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='low',
            threshold_value=50.0
        )
        
        self.threshold_profile.apply_to_rule(alert_rule)
        
        alert_rule.refresh_from_db()
        self.assertEqual(alert_rule.severity, 'high')
        self.assertEqual(alert_rule.threshold_value, 70.0)  # Warning threshold
    
    def test_threshold_profile_get_rules_count(self):
        """Test ThresholdProfile get rules count"""
        # Initially should be 0
        self.assertEqual(self.threshold_profile.get_rules_count(), 0)
        
        # Add some rules
        for i in range(3):
            AlertRule.objects.create(
                name=f'Alert {i}',
                alert_type='cpu_usage',
                severity='high',
                threshold_value=80.0
            )
        
        # Associate rules with profile (this would be done through a relationship)
        # For now, we'll test the method assuming the relationship exists
        count = self.threshold_profile.get_rules_count()
        # This would return the actual count based on the relationship
        self.assertIsInstance(count, int)
    
    def test_threshold_profile_get_type_display(self):
        """Test ThresholdProfile type display"""
        self.assertEqual(self.threshold_profile.get_type_display(), 'Environment')
        
        self.threshold_profile.profile_type = 'service'
        self.assertEqual(self.threshold_profile.get_type_display(), 'Service')
        
        self.threshold_profile.profile_type = 'custom'
        self.assertEqual(self.threshold_profile.get_type_display(), 'Custom')
