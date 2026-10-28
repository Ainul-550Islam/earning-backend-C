"""
Tests for Intelligence Signals — FIXED
Covers: correlation_created, correlation_updated, prediction_created,
        anomaly_detected, noise_filtered, root_cause_identified, rca_completed.
"""
from django.test import TestCase

from api.alerts.models.intelligence import AlertCorrelation, RootCauseAnalysis, AlertPrediction, AlertNoise
from api.alerts.signals.intelligence import (
    correlation_created, correlation_updated, correlation_detected,
    prediction_created, anomaly_detected, noise_filtered,
    root_cause_identified, rca_created, rca_completed,
    correlation_analyzed, noise_filter_created, prediction_trained, prediction_made,
)


class CorrelationSignalsTest(TestCase):
    """Tests for AlertCorrelation signals"""

    def setUp(self):
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_correlation_created_signal(self):
        """correlation_created fires on new AlertCorrelation"""
        correlation_created.connect(self._handler)
        AlertCorrelation.objects.create(
            name='Signal Correlation', correlation_type='temporal',
            correlation_strength=0.9, is_active=True, time_window_minutes=60)
        self.assertTrue(self.signal_received)
        correlation_created.disconnect(self._handler)

    def test_correlation_updated_signal(self):
        """correlation_updated fires on AlertCorrelation update"""
        corr = AlertCorrelation.objects.create(
            name='Update Correlation', correlation_type='statistical',
            correlation_strength=0.7, is_active=True, time_window_minutes=30)
        self.signal_received = False
        correlation_updated.connect(self._handler)
        corr.correlation_strength = 0.8
        corr.save()
        self.assertTrue(self.signal_received)
        correlation_updated.disconnect(self._handler)

    def test_correlation_detected_signal_fires_when_significant(self):
        """correlation_detected fires when analyze_correlation finds a significant correlation"""
        from api.alerts.models.core import AlertRule, AlertLog
        from django.utils import timezone
        from datetime import timedelta
        primary_rule = AlertRule.objects.create(
            name='Corr Primary Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30)
        secondary_rule = AlertRule.objects.create(
            name='Corr Secondary Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30)
        now = timezone.now()
        # Identical counts across both rules on the same days => a real, strong
        # positive Pearson correlation once analyze_correlation recomputes it.
        for days_ago, count in [(0, 3), (5, 1), (10, 2), (15, 4)]:
            day = now - timedelta(days=days_ago)
            for _ in range(count):
                AlertLog.objects.create(rule=primary_rule, trigger_value=90.0,
                                        threshold_value=80.0, message='p', triggered_at=day)
                AlertLog.objects.create(rule=secondary_rule, trigger_value=90.0,
                                        threshold_value=80.0, message='s', triggered_at=day)
        corr = AlertCorrelation.objects.create(
            name='Detected Correlation', correlation_type='statistical',
            correlation_strength=0.9, is_active=True, time_window_minutes=60,
            correlation_threshold=0.5)
        corr.primary_rules.add(primary_rule)
        corr.secondary_rules.add(secondary_rule)
        correlation_detected.connect(self._handler)
        corr.analyze_correlation()
        self.assertTrue(self.signal_received)
        correlation_detected.disconnect(self._handler)

    def test_correlation_created_payload_has_instance(self):
        payload = {}
        def capture(sender, **kwargs):
            payload.update(kwargs)
        correlation_created.connect(capture)
        corr = AlertCorrelation.objects.create(
            name='Payload Correlation', correlation_type='causal',
            is_active=True, time_window_minutes=45)
        self.assertIn('instance', payload)
        self.assertEqual(payload['instance'], corr)
        correlation_created.disconnect(capture)


class PredictionSignalsTest(TestCase):
    """Tests for AlertPrediction signals"""

    def setUp(self):
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_prediction_created_signal_fires_on_create(self):
        prediction_created.connect(self._handler)
        AlertPrediction.objects.create(
            name='Signal Prediction', prediction_type='volume',
            model_type='linear_regression', training_status='pending')
        self.assertTrue(self.signal_received)
        prediction_created.disconnect(self._handler)

    def test_anomaly_detected_signal_fires_when_detected_at_set(self):
        from api.alerts.models.intelligence import AnomalyDetectionModel
        from api.alerts.models.core import AlertRule
        rule = AlertRule.objects.create(
            name='Anomaly Signal Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30)
        model = AnomalyDetectionModel.objects.create(
            name='Signal Anomaly Model', detection_method='statistical',
            is_active=True, sensitivity=0.8, window_size_minutes=60,
            baseline_days=7, anomaly_threshold=2.0, min_alert_count=3)
        model.target_rules.set([rule])
        anomaly_detected.connect(self._handler)
        from django.utils import timezone
        model.last_anomaly_detected_at = timezone.now()
        model.save()
        self.assertTrue(self.signal_received)
        anomaly_detected.disconnect(self._handler)

    def test_noise_filtered_signal_fires_on_match(self):
        from api.alerts.models.intelligence import AlertNoise
        from api.alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='Noise Signal Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30)
        log = AlertLog.objects.create(
            rule=rule, trigger_value=90.0, threshold_value=80.0, message='Noisy alert')
        noise = AlertNoise.objects.create(
            name='Signal Noise Filter', noise_type='repeated', action='suppress', is_active=True)
        noise_filtered.connect(self._handler)
        noise.process_alert(log)
        self.assertTrue(self.signal_received)
        noise_filtered.disconnect(self._handler)


class RCASignalsTest(TestCase):
    """Tests for RootCauseAnalysis signals"""

    def setUp(self):
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_rca_created_signal_fires(self):
        """rca_created fires on new RootCauseAnalysis"""
        rca_created.connect(self._handler)
        RootCauseAnalysis.objects.create(
            title='RCA Signal Test',
            description='',
            analysis_method='5_whys',
            status='draft')
        self.assertTrue(self.signal_received)
        rca_created.disconnect(self._handler)

    def test_rca_completed_signal_fires_on_perform_analysis(self):
        from api.alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='RCA Signal Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30)
        log = AlertLog.objects.create(
            rule=rule, trigger_value=90.0, threshold_value=80.0, message='RCA test alert')
        rca = RootCauseAnalysis.objects.create(
            title='RCA Completed Signal Test', description='', analysis_method='5_whys', status='draft')
        rca.related_alerts.add(log)
        rca_completed.connect(self._handler)
        rca.perform_analysis()
        self.assertTrue(self.signal_received)
        self.assertEqual(rca.status, 'completed')
        rca_completed.disconnect(self._handler)

    def test_root_cause_identified_signal_fires_when_cause_found(self):
        from api.alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='Root Cause Signal Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30)
        log = AlertLog.objects.create(
            rule=rule, trigger_value=90.0, threshold_value=80.0, message='Root cause test alert')
        rca = RootCauseAnalysis.objects.create(
            title='Root Cause Identified Signal Test', description='', analysis_method='5_whys', status='draft')
        rca.related_alerts.add(log)
        root_cause_identified.connect(self._handler)
        rca.perform_analysis()
        self.assertTrue(self.signal_received)
        self.assertTrue(rca.root_causes)
        root_cause_identified.disconnect(self._handler)

    def test_rca_payload_has_instance(self):
        payload = {}
        def capture(sender, **kwargs):
            payload.update(kwargs)
        rca_created.connect(capture)
        rca = RootCauseAnalysis.objects.create(
            title='RCA Payload Test',
            description='',
            analysis_method='fault_tree',
            status='draft')
        self.assertIn('instance', payload)
        self.assertEqual(payload['instance'], rca)
        rca_created.disconnect(capture)


class NewlyWiredIntelligenceSignalsTest(TestCase):
    """Real behavioral tests for 4 more signals confirmed never fired anywhere
    before this session."""

    def setUp(self):
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_correlation_analyzed_signal_fires_on_every_analysis(self):
        # Unlike correlation_detected (only fires when significant),
        # correlation_analyzed should fire even with no real correlation found.
        corr = AlertCorrelation.objects.create(
            name='Analyzed Signal Correlation', correlation_type='temporal',
            correlation_strength=0.5, is_active=True, time_window_minutes=60,
            correlation_threshold=0.99)
        correlation_analyzed.connect(self._handler)
        corr.analyze_correlation()
        self.assertTrue(self.signal_received)
        correlation_analyzed.disconnect(self._handler)

    def test_noise_filter_created_signal(self):
        noise_filter_created.connect(self._handler)
        AlertNoise.objects.create(name='Signal Noise Filter Rule', action='suppress')
        self.assertTrue(self.signal_received)
        noise_filter_created.disconnect(self._handler)

    def test_prediction_trained_signal_fires_on_successful_training(self):
        prediction = AlertPrediction.objects.create(
            name='Trained Signal Prediction', prediction_type='volume',
            model_type='linear_regression', training_status='pending')
        prediction_trained.connect(self._handler)
        prediction.train_model()
        self.assertTrue(self.signal_received)
        self.assertEqual(prediction.training_status, 'completed')
        prediction_trained.disconnect(self._handler)

    def test_prediction_made_signal_fires_on_make_prediction(self):
        prediction = AlertPrediction.objects.create(
            name='Made Signal Prediction', prediction_type='volume',
            model_type='linear_regression', training_status='completed')
        prediction_made.connect(self._handler)
        result = prediction.make_prediction()
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(result)
        prediction_made.disconnect(self._handler)
