"""
Tests for Threshold Signals — FIXED
Covers: threshold_config_created, threshold_config_updated,
        threshold_breach_created, threshold_breach_resolved,
        threshold_breach_acknowledged, adaptive_threshold_created signals.
"""
from django.test import TestCase
from django.utils import timezone

from api.alerts.models.core import AlertRule
from api.alerts.models.threshold import ThresholdConfig, ThresholdBreach, AdaptiveThreshold, ThresholdHistory, ThresholdProfile
from api.alerts.signals.threshold import (
    threshold_config_created, threshold_config_updated,
    threshold_breach_created, threshold_breach_resolved,
    threshold_breach_acknowledged, adaptive_threshold_created,
    adaptive_threshold_updated, threshold_history_created, threshold_profile_applied,
)


def _make_rule(name='Threshold Signal Rule'):
    return AlertRule.objects.create(
        name=name, alert_type='server_error', severity='high', threshold_value=80.0)


def _make_config(rule, name='Signal Config'):
    return ThresholdConfig.objects.create(
        name=name, alert_rule=rule, threshold_type='static',
        primary_threshold=80.0, comparison_operator='gt', is_active=True)


class ThresholdConfigSignalsTest(TestCase):
    """Tests for ThresholdConfig signals"""

    def setUp(self):
        self.signal_received = False
        self.signal_data = {}
        self.rule = _make_rule()

    def _handler(self, sender, **kwargs):
        self.signal_received = True
        self.signal_data = kwargs

    def test_threshold_config_created_signal(self):
        threshold_config_created.connect(self._handler)
        config = _make_config(self.rule)
        self.assertTrue(self.signal_received)
        self.assertIn('instance', self.signal_data)
        threshold_config_created.disconnect(self._handler)

    def test_threshold_config_updated_signal(self):
        config = _make_config(self.rule, 'Update Signal Config')
        self.signal_received = False
        threshold_config_updated.connect(self._handler)
        config.primary_threshold = 90.0
        config.save()
        self.assertTrue(self.signal_received)
        threshold_config_updated.disconnect(self._handler)

    def test_config_disable_fires_update_signal(self):
        config = _make_config(self.rule, 'Disable Signal Config')
        threshold_config_updated.connect(self._handler)
        self.signal_received = False
        config.is_active = False
        config.save()
        self.assertTrue(self.signal_received)
        threshold_config_updated.disconnect(self._handler)

    def test_threshold_config_signal_payload(self):
        payload = {}
        def capture(sender, **kwargs):
            payload.update(kwargs)
        threshold_config_created.connect(capture)
        config = _make_config(self.rule, 'Payload Config')
        self.assertIn('instance', payload)
        self.assertEqual(payload['instance'], config)
        threshold_config_created.disconnect(capture)


class ThresholdBreachSignalsTest(TestCase):
    """Tests for ThresholdBreach signals"""

    def setUp(self):
        self.signal_received = False
        self.rule = _make_rule('Breach Signal Rule')
        self.config = _make_config(self.rule, 'Breach Signal Config')

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_threshold_breach_created_signal(self):
        threshold_breach_created.connect(self._handler)
        ThresholdBreach.objects.create(
            threshold_config=self.config, breach_value=90.0,
            threshold_value=80.0, severity='high', status='open')
        self.assertTrue(self.signal_received)
        threshold_breach_created.disconnect(self._handler)

    def test_threshold_breach_resolved_signal_fires_on_resolve(self):
        breach = ThresholdBreach.objects.create(
            threshold_config=self.config, breach_value=90.0,
            threshold_value=80.0, severity='high', status='open')
        threshold_breach_resolved.connect(self._handler)
        breach.resolve(user=None, notes='Fixed')
        self.assertTrue(self.signal_received)
        threshold_breach_resolved.disconnect(self._handler)

    def test_threshold_breach_acknowledged_signal_fires_on_acknowledge(self):
        breach = ThresholdBreach.objects.create(
            threshold_config=self.config, breach_value=90.0,
            threshold_value=80.0, severity='high', status='open')
        threshold_breach_acknowledged.connect(self._handler)
        breach.acknowledge(user=None, notes='Looking into it')
        self.assertTrue(self.signal_received)
        threshold_breach_acknowledged.disconnect(self._handler)

    def test_resolve_breach_updates_status(self):
        breach = ThresholdBreach.objects.create(
            threshold_config=self.config, breach_value=90.0,
            threshold_value=80.0, severity='high', status='open')
        breach.status = 'resolved'
        breach.resolved_at = timezone.now()
        breach.save()
        breach.refresh_from_db()
        self.assertEqual(breach.status, 'resolved')


class AdaptiveThresholdSignalsTest(TestCase):
    """Tests for AdaptiveThreshold signals"""

    def setUp(self):
        self.signal_received = False
        self.rule = _make_rule('Adaptive Signal Rule')
        self.config = _make_config(self.rule, 'Adaptive Signal Config')

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_adaptive_threshold_created_signal(self):
        adaptive_threshold_created.connect(self._handler)
        adaptive = AdaptiveThreshold.objects.create(
            name='Signal Adaptive', threshold_config=self.config,
            adaptation_method='exponential_smoothing', base_threshold=80.0,
            current_threshold=80.0, min_threshold=50.0, max_threshold=150.0)
        self.assertTrue(self.signal_received)
        adaptive_threshold_created.disconnect(self._handler)

    def test_adaptive_threshold_updated_signal(self):
        adaptive = AdaptiveThreshold.objects.create(
            name='Update Adaptive', threshold_config=self.config,
            adaptation_method='exponential_smoothing', base_threshold=80.0,
            current_threshold=80.0, min_threshold=50.0, max_threshold=150.0)
        self.signal_received = False
        adaptive_threshold_updated.connect(self._handler)
        adaptive.current_threshold = 85.0
        adaptive.save()
        self.assertTrue(self.signal_received)
        adaptive_threshold_updated.disconnect(self._handler)


class NewlyWiredThresholdSignalsTest(TestCase):
    """Real behavioral tests for threshold_history_created and
    threshold_profile_applied, confirmed never fired anywhere before."""

    def setUp(self):
        self.rule = _make_rule('New Threshold Signals Rule')
        self.config = _make_config(self.rule, 'New Threshold Signals Config')
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_threshold_history_created_signal(self):
        adaptive = AdaptiveThreshold.objects.create(
            name='History Signal Adaptive', threshold_config=self.config,
            adaptation_method='exponential_smoothing', base_threshold=80.0,
            current_threshold=80.0, min_threshold=50.0, max_threshold=150.0)
        threshold_history_created.connect(self._handler)
        ThresholdHistory.objects.create(
            adaptive_threshold=adaptive, change_type='increase',
            old_threshold=80.0, new_threshold=90.0, change_percentage=12.5,
            reason='Signal test')
        self.assertTrue(self.signal_received)
        threshold_history_created.disconnect(self._handler)

    def test_threshold_profile_applied_signal(self):
        profile = ThresholdProfile.objects.create(
            name='Signal Profile', profile_type='balanced', description='test',
            default_threshold_multiplier=1.2)
        threshold_profile_applied.connect(self._handler)
        profile.apply_to_threshold_config(self.config)
        self.assertTrue(self.signal_received)
        threshold_profile_applied.disconnect(self._handler)
