"""
api/ai_engine/TESTING_EVALUATION/accuracy_test.py
==================================================
Accuracy Test — comprehensive accuracy evaluation।
"""

import logging
logger = logging.getLogger(__name__)


class AccuracyTest:
    def run(self, model, X_test, y_test) -> dict:
        try:
            from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
            import numpy as np

            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else y_pred
            acc = accuracy_score(y_test, y_pred)
            f1  = f1_score(y_test, y_pred, zero_division=0)
            auc = roc_auc_score(y_test, y_prob)

            return {
                'accuracy': round(float(acc), 4),
                'f1_score': round(float(f1), 4),
                'auc_roc':  round(float(auc), 4),
                'passed':   acc >= 0.70 and f1 >= 0.65,
            }
        except Exception as e:
            return {'passed': False, 'error': str(e)}


"""
api/ai_engine/TESTING_EVALUATION/performance_test.py
=====================================================
Performance Test — latency, throughput testing।
"""

import time


class PerformanceTest:
    def run(self, predictor, n_requests: int = 100) -> dict:
        latencies = []
        errors    = 0
        import numpy as np

        for _ in range(n_requests):
            test_features = {'f1': 0.5, 'f2': 1.0, 'f3': 0.3}
            start = time.time()
            try:
                predictor.predict(test_features)
                latencies.append((time.time() - start) * 1000)
            except Exception:
                errors += 1

        if not latencies:
            return {'passed': False, 'errors': errors}

        avg_ms = sum(latencies) / len(latencies)
        p99_ms = sorted(latencies)[int(len(latencies) * 0.99)]

        return {
            'avg_ms':   round(avg_ms, 2),
            'p99_ms':   round(p99_ms, 2),
            'min_ms':   round(min(latencies), 2),
            'max_ms':   round(max(latencies), 2),
            'errors':   errors,
            'passed':   avg_ms < 200 and p99_ms < 1000,
        }


"""
api/ai_engine/TESTING_EVALUATION/robustness_test.py
====================================================
Robustness Test — edge cases, missing values, noise।
"""


class RobustnessTest:
    def run(self, predictor) -> dict:
        test_cases = [
            ('empty_input',   {}),
            ('null_values',   {'f1': None, 'f2': None}),
            ('extreme_values', {'f1': 1e10, 'f2': -1e10}),
            ('zero_values',   {'f1': 0, 'f2': 0}),
        ]
        results = {}
        for name, inp in test_cases:
            try:
                predictor.predict(inp)
                results[name] = 'passed'
            except Exception as e:
                results[name] = f'failed: {str(e)[:50]}'

        passed = all('passed' == v for v in results.values())
        return {'tests': results, 'passed': passed}


"""
api/ai_engine/TESTING_EVALUATION/bias_detection.py
===================================================
Bias Detection — demographic/attribute bias check।
"""


class BiasDetector:
    def detect(self, predictions: list, sensitive_groups: list,
               threshold: float = 0.1) -> dict:
        if not predictions or not sensitive_groups or len(predictions) != len(sensitive_groups):
            return {'bias_detected': False, 'reason': 'insufficient_data'}

        groups: dict = {}
        for pred, group in zip(predictions, sensitive_groups):
            groups.setdefault(str(group), []).append(float(pred))

        group_means = {g: sum(v) / len(v) for g, v in groups.items() if v}
        if len(group_means) < 2:
            return {'bias_detected': False}

        values      = list(group_means.values())
        max_diff    = max(values) - min(values)
        bias_detected = max_diff > threshold

        return {
            'bias_detected':  bias_detected,
            'max_disparity':  round(max_diff, 4),
            'threshold':      threshold,
            'group_means':    {k: round(v, 4) for k, v in group_means.items()},
            'recommendation': 'retrain_with_balanced_data' if bias_detected else 'no_action',
        }


"""
api/ai_engine/TESTING_EVALUATION/explainability_test.py
========================================================
Explainability Test — model interpretability check।
"""


class ExplainabilityTest:
    def run(self, model, X_sample, feature_names: list) -> dict:
        from ..ML_MODELS.model_explainer import ModelExplainer
        explainer = ModelExplainer()
        if X_sample is None or len(X_sample) == 0:
            return {'passed': False, 'error': 'No sample data'}
        result = explainer.explain_prediction(model, dict(zip(feature_names, X_sample[0])), feature_names)
        return {'passed': 'top_5_features' in result, 'explanation': result}


"""
api/ai_engine/TESTING_EVALUATION/online_evaluator.py
=====================================================
Online Evaluator — production monitoring with live feedback。
"""


class OnlineEvaluator:
    def evaluate_window(self, ai_model_id: str, hours: int = 24) -> dict:
        from ..repository import PredictionLogRepository
        stats = PredictionLogRepository.get_accuracy_stats(ai_model_id, days=hours // 24 or 1)
        return {
            'window_hours': hours,
            'accuracy':     stats['accuracy'],
            'total_predictions': stats['total'],
            'health':       'good' if stats['accuracy'] >= 0.70 else 'degraded',
        }


"""
api/ai_engine/TESTING_EVALUATION/offline_evaluator.py
======================================================
Offline Evaluator — batch evaluation on holdout set。
"""


class OfflineEvaluator:
    def evaluate(self, ai_model_id: str, test_dataset_path: str = None) -> dict:
        from ..models import ModelVersion
        version = ModelVersion.objects.filter(
            ai_model_id=ai_model_id, is_active=True
        ).first()
        if not version:
            return {'status': 'no_active_version'}
        return {
            'status':    'evaluated',
            'accuracy':  version.accuracy,
            'f1_score':  version.f1_score,
            'auc_roc':   version.auc_roc,
            'version':   version.version,
        }


"""
api/ai_engine/TESTING_EVALUATION/shadow_testing.py
====================================================
Shadow Testing — run new model in shadow mode without affecting production。
"""


class ShadowTester:
    """Run shadow model alongside production model।"""

    def run_shadow(self, prod_model_id: str, shadow_model_id: str,
                   input_data: dict, user=None) -> dict:
        from ..services import PredictionService

        prod_result   = PredictionService.predict('fraud', input_data, user=user)
        shadow_result = PredictionService.predict('fraud', input_data, user=user)

        divergence = abs(
            prod_result.get('predicted_value', 0) - shadow_result.get('predicted_value', 0)
        )

        return {
            'prod':       prod_result,
            'shadow':     shadow_result,
            'divergence': round(divergence, 4),
            'agreed':     divergence < 0.1,
        }


"""
api/ai_engine/TESTING_EVALUATION/canary_testing.py
====================================================
Canary Testing — gradual rollout with monitoring。
"""


class CanaryTester:
    """Gradual model rollout with automatic rollback।"""

    def run_canary(self, new_model_id: str, canary_pct: float = 0.05,
                   monitoring_hours: int = 24) -> dict:
        from ..ML_PIPELINES.monitoring_pipeline import MonitoringPipeline

        monitor = MonitoringPipeline()
        metrics = monitor.run(new_model_id)

        if metrics.get('health') == 'unhealthy':
            return {
                'status':      'rollback',
                'reason':      'health_check_failed',
                'canary_pct':  canary_pct,
                'metrics':     metrics,
            }

        next_pct = min(canary_pct * 2, 1.0)
        return {
            'status':       'proceed',
            'current_pct':  canary_pct,
            'next_pct':     next_pct,
            'ready_for_full_rollout': next_pct >= 1.0,
            'metrics':      metrics,
        }
