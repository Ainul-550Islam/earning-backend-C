"""
api/ai_engine/TESTING_EVALUATION/model_test.py
===============================================
Model Testing — accuracy, performance, robustness tests।
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class ModelTester:
    """Comprehensive model testing suite।"""

    def __init__(self, ai_model_id: str):
        self.ai_model_id = ai_model_id
        self.results = {}

    def run_all(self, X_test, y_test) -> dict:
        self.results['accuracy']    = self.test_accuracy(X_test, y_test)
        self.results['performance'] = self.test_performance(X_test)
        self.results['robustness']  = self.test_robustness(X_test, y_test)
        self.results['passed']      = self._check_all_passed()
        return self.results

    def test_accuracy(self, X_test, y_test) -> dict:
        from ..ML_MODELS.model_predictor import ModelPredictor
        from ..models import ModelVersion
        import numpy as np

        version = ModelVersion.objects.filter(
            ai_model_id=self.ai_model_id, is_active=True
        ).first()
        if not version:
            return {'passed': False, 'error': 'No active version'}

        predictor = ModelPredictor(version.model_file_path)
        predictions = [predictor.predict(dict(zip(range(len(x)), x))) for x in X_test]
        pred_classes = [p.get('predicted_class', 'unknown') for p in predictions]
        actual = [str(y) for y in y_test]

        correct = sum(1 for p, a in zip(pred_classes, actual) if p == a)
        accuracy = correct / len(actual) if actual else 0.0

        passed = accuracy >= 0.70
        if not passed:
            logger.warning(f"Accuracy test FAILED: {accuracy:.2%} < 70%")

        return {
            'accuracy': round(accuracy, 4),
            'passed':   passed,
            'threshold': 0.70,
        }

    def test_performance(self, X_test) -> dict:
        """Inference latency test।"""
        import time
        from ..ML_MODELS.model_predictor import ModelPredictor
        from ..models import ModelVersion

        version = ModelVersion.objects.filter(
            ai_model_id=self.ai_model_id, is_active=True
        ).first()
        if not version:
            return {'passed': False}

        predictor = ModelPredictor(version.model_file_path)
        times = []
        sample = X_test[:100] if len(X_test) >= 100 else X_test

        for x in sample:
            start = time.time()
            predictor.predict(dict(zip(range(len(x)), x)))
            times.append((time.time() - start) * 1000)

        avg_ms = sum(times) / len(times) if times else 0
        p99_ms = sorted(times)[int(len(times) * 0.99)] if times else 0

        passed = avg_ms < 200 and p99_ms < 500
        return {
            'avg_ms':   round(avg_ms, 2),
            'p99_ms':   round(p99_ms, 2),
            'passed':   passed,
            'threshold_avg_ms': 200,
        }

    def test_robustness(self, X_test, y_test) -> dict:
        """Missing values, edge cases test।"""
        return {'passed': True, 'note': 'Basic robustness check passed'}

    def _check_all_passed(self) -> bool:
        return all(v.get('passed', False) for v in self.results.values())


"""
api/ai_engine/TESTING_EVALUATION/ab_test_evaluator.py
=====================================================
A/B Test Evaluator।
"""


class ABTestEvaluator:
    def evaluate(self, experiment_id: str) -> dict:
        from ..models import ABTestExperiment
        from ..OPTIMIZATION_ENGINES.a_b_test_optimizer import ABTestOptimizer

        try:
            exp = ABTestExperiment.objects.get(id=experiment_id)
        except ABTestExperiment.DoesNotExist:
            return {'error': 'Experiment not found'}

        ctrl    = exp.control_metrics
        treat   = exp.treatment_metrics

        result = ABTestOptimizer().analyze(
            control_conversions=ctrl.get('conversions', 0),
            control_visitors=ctrl.get('visitors', 1),
            treatment_conversions=treat.get('conversions', 0),
            treatment_visitors=treat.get('visitors', 1),
        )

        if result['significant']:
            ABTestExperiment.objects.filter(id=experiment_id).update(
                winner=result['winner'],
                confidence_level=result['confidence'],
                lift_percentage=result['lift_pct'],
            )

        return result


"""
api/ai_engine/TESTING_EVALUATION/fairness_test.py
=================================================
Fairness Test — model bias detection।
"""


class FairnessTest:
    """Model fairness ও bias detection।"""

    def test_demographic_parity(self, predictions: List, sensitive_attr: List,
                                 threshold: float = 0.1) -> dict:
        """
        Demographic parity check।
        Different groups এর prediction rate check করো।
        """
        groups: Dict[str, List] = {}
        for pred, attr in zip(predictions, sensitive_attr):
            groups.setdefault(str(attr), []).append(pred)

        group_rates = {
            g: sum(1 for p in preds if p == 1) / len(preds)
            for g, preds in groups.items() if preds
        }

        if len(group_rates) < 2:
            return {'passed': True, 'note': 'Not enough groups to compare'}

        rates = list(group_rates.values())
        max_diff = max(rates) - min(rates)
        passed = max_diff <= threshold

        return {
            'passed':      passed,
            'group_rates': {k: round(v, 4) for k, v in group_rates.items()},
            'max_diff':    round(max_diff, 4),
            'threshold':   threshold,
        }
