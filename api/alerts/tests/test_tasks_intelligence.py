"""
Tests for Intelligence Tasks — FIXED
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from api.alerts.models.intelligence import (
    AlertCorrelation, AlertPrediction, AlertNoise, RootCauseAnalysis,
)
from api.alerts.models.core import AlertRule

User = get_user_model()


def _make_rule(name='Intel Task Rule'):
    return AlertRule.objects.create(
        name=name, alert_type='server_error', severity='high', threshold_value=80.0)


class AnalyzeAllCorrelationsTaskTest(TestCase):

    def test_task_runs_with_no_data(self):
        from api.alerts.tasks.intelligence import analyze_all_correlations
        try:
            analyze_all_correlations()
        except Exception as e:
            self.fail(f"analyze_all_correlations raised unexpectedly: {e}")

    def test_task_processes_existing_correlations(self):
        AlertCorrelation.objects.create(
            name='Analyze Correlation', correlation_type='temporal',
            is_active=True, time_window_minutes=30)
        from api.alerts.tasks.intelligence import analyze_all_correlations
        try:
            analyze_all_correlations()
        except Exception as e:
            self.fail(f"analyze_all_correlations raised unexpectedly: {e}")


class TrainPredictionModelsTaskTest(TestCase):

    def test_task_runs_with_no_data(self):
        from api.alerts.tasks.intelligence import train_prediction_models
        try:
            train_prediction_models()
        except Exception as e:
            self.fail(f"train_prediction_models raised unexpectedly: {e}")

    def test_task_with_active_prediction(self):
        AlertPrediction.objects.create(
            name='Task Prediction', prediction_type='volume',
            model_type='linear_regression', is_active=True)
        from api.alerts.tasks.intelligence import train_prediction_models
        try:
            train_prediction_models()
        except Exception as e:
            self.fail(f"train_prediction_models raised unexpectedly: {e}")


class DetectAnomaliesTaskTest(TestCase):

    def test_task_runs_with_no_data(self):
        from api.alerts.tasks.intelligence import detect_anomalies
        try:
            detect_anomalies()
        except Exception as e:
            self.fail(f"detect_anomalies raised unexpectedly: {e}")


class OptimizeNoiseFiltersTaskTest(TestCase):

    def test_task_runs_with_no_filters(self):
        from api.alerts.tasks.intelligence import optimize_noise_filters
        try:
            optimize_noise_filters()
        except Exception as e:
            self.fail(f"optimize_noise_filters raised unexpectedly: {e}")

    def test_task_processes_active_filter(self):
        # Use correct field names from AlertNoise model
        AlertNoise.objects.create(
            name='Task Noise Filter',
            noise_type='repeated',
            filter_type='rate_limit',
            is_active=True,
            suppression_window_minutes=15)
        from api.alerts.tasks.intelligence import optimize_noise_filters
        try:
            optimize_noise_filters()
        except Exception as e:
            self.fail(f"optimize_noise_filters raised unexpectedly: {e}")


class RunIntelligencePipelineTaskTest(TestCase):

    def test_full_pipeline_runs(self):
        from api.alerts.tasks.intelligence import run_intelligence_pipeline
        try:
            run_intelligence_pipeline()
        except Exception as e:
            self.fail(f"run_intelligence_pipeline raised unexpectedly: {e}")


class EvaluateModelAccuracyTaskTest(TestCase):

    def test_task_runs(self):
        from api.alerts.tasks.intelligence import evaluate_model_accuracy
        try:
            evaluate_model_accuracy()
        except Exception as e:
            self.fail(f"evaluate_model_accuracy raised unexpectedly: {e}")


class CleanupOldIntelligenceDataTaskTest(TestCase):

    def test_cleanup_task_runs(self):
        from api.alerts.tasks.intelligence import cleanup_old_intelligence_data
        try:
            cleanup_old_intelligence_data()
        except Exception as e:
            self.fail(f"cleanup_old_intelligence_data raised unexpectedly: {e}")


class OptimizeIntelligenceModelsTaskTest(TestCase):

    def test_optimization_task_runs(self):
        from api.alerts.tasks.intelligence import optimize_intelligence_models
        try:
            optimize_intelligence_models()
        except Exception as e:
            self.fail(f"optimize_intelligence_models raised unexpectedly: {e}")

    def test_train_correlation_model_valid_id(self):
        corr = AlertCorrelation.objects.create(
            name='Train Correlation', correlation_type='causal',
            correlation_strength=0.75, is_active=True, time_window_minutes=30)
        from api.alerts.tasks.intelligence import train_correlation_model
        try:
            train_correlation_model(corr.id)
        except Exception as e:
            self.fail(f"train_correlation_model raised unexpectedly: {e}")

    def test_test_prediction_model_valid_id(self):
        model = AlertPrediction.objects.create(
            name='Test Prediction', prediction_type='classification',
            model_type='random_forest', algorithm='random_forest', is_active=True)
        from api.alerts.tasks.intelligence import test_prediction_model
        try:
            test_prediction_model(model.id)
        except Exception as e:
            self.fail(f"test_prediction_model raised unexpectedly: {e}")


class UpdateCorrelationInsightsTaskTest(TestCase):

    def test_task_runs(self):
        from api.alerts.tasks.intelligence import update_correlation_insights
        try:
            update_correlation_insights()
        except Exception as e:
            self.fail(f"update_correlation_insights raised unexpectedly: {e}")


class UpdateNoiseEffectivenessTaskTest(TestCase):

    def test_task_runs(self):
        from api.alerts.tasks.intelligence import update_noise_effectiveness
        try:
            update_noise_effectiveness()
        except Exception as e:
            self.fail(f"update_noise_effectiveness raised unexpectedly: {e}")
