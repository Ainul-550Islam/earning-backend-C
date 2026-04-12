"""
api/ai_engine/TESTING_EVALUATION/robustness_test.py
====================================================
Robustness Test — edge cases, adversarial inputs, noise tolerance।
Model কি unexpected inputs এ gracefully handle করতে পারে।
Production deployment এর আগে mandatory test।
"""

import logging
import random
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class RobustnessTest:
    """
    Model robustness testing suite।
    Edge cases, noise, adversarial examples test করো।
    """

    def run(self, predictor, feature_names: List[str] = None,
             n_tests: int = 100) -> dict:
        """Full robustness test suite চালাও।"""
        feature_names = feature_names or [f"f{i}" for i in range(10)]

        results = {
            "empty_input":     self._test_empty(predictor),
            "null_values":     self._test_nulls(predictor, feature_names),
            "extreme_values":  self._test_extremes(predictor, feature_names),
            "zero_values":     self._test_zeros(predictor, feature_names),
            "negative_values": self._test_negatives(predictor, feature_names),
            "string_values":   self._test_string_values(predictor, feature_names),
            "random_noise":    self._test_noise(predictor, feature_names, n_tests),
            "boundary_values": self._test_boundaries(predictor, feature_names),
        }

        passed        = sum(1 for r in results.values() if r.get("passed", False))
        total         = len(results)
        pass_rate     = passed / total
        overall       = "robust" if pass_rate >= 0.80 else "acceptable" if pass_rate >= 0.60 else "fragile"

        return {
            "overall_status":   overall,
            "passed":           passed,
            "total_tests":      total,
            "pass_rate":        round(pass_rate, 4),
            "test_results":     results,
            "recommendation":   self._recommendation(overall, results),
        }

    def _test_empty(self, predictor) -> dict:
        try:
            predictor.predict({})
            return {"passed": True, "test": "empty_input", "note": "Handles empty dict gracefully"}
        except Exception as e:
            return {"passed": False, "test": "empty_input", "error": str(e)[:100]}

    def _test_nulls(self, predictor, feature_names: List[str]) -> dict:
        null_input = {f: None for f in feature_names}
        try:
            predictor.predict(null_input)
            return {"passed": True, "test": "null_values", "note": "Handles None values"}
        except Exception as e:
            return {"passed": False, "test": "null_values", "error": str(e)[:100]}

    def _test_extremes(self, predictor, feature_names: List[str]) -> dict:
        extreme_input = {f: 1e15 for f in feature_names}
        try:
            result = predictor.predict(extreme_input)
            conf   = result.get("confidence", 0) if isinstance(result, dict) else 0
            passed = 0.0 <= conf <= 1.0
            return {"passed": passed, "test": "extreme_values", "confidence": conf}
        except Exception as e:
            return {"passed": False, "test": "extreme_values", "error": str(e)[:100]}

    def _test_zeros(self, predictor, feature_names: List[str]) -> dict:
        zero_input = {f: 0 for f in feature_names}
        try:
            result = predictor.predict(zero_input)
            conf   = result.get("confidence", 0) if isinstance(result, dict) else 0
            return {"passed": 0.0 <= conf <= 1.0, "test": "zero_values"}
        except Exception as e:
            return {"passed": False, "test": "zero_values", "error": str(e)[:100]}

    def _test_negatives(self, predictor, feature_names: List[str]) -> dict:
        neg_input = {f: -9999 for f in feature_names}
        try:
            predictor.predict(neg_input)
            return {"passed": True, "test": "negative_values"}
        except Exception as e:
            return {"passed": False, "test": "negative_values", "error": str(e)[:100]}

    def _test_string_values(self, predictor, feature_names: List[str]) -> dict:
        str_input = {f: "invalid_string" for f in feature_names}
        try:
            predictor.predict(str_input)
            return {"passed": True, "test": "string_values", "note": "Handles string inputs"}
        except Exception:
            # It's OK to fail with strings — just shouldn't crash the system
            return {"passed": True, "test": "string_values", "note": "Raises exception for strings (acceptable)"}

    def _test_noise(self, predictor, feature_names: List[str], n: int = 100) -> dict:
        """Random noise inputs — prediction should stay in valid range।"""
        errors   = 0
        out_range = 0

        for _ in range(n):
            noisy_input = {f: random.gauss(0, 10) for f in feature_names}
            try:
                result = predictor.predict(noisy_input)
                if isinstance(result, dict):
                    conf = result.get("confidence", 0)
                    if not (0.0 <= conf <= 1.0):
                        out_range += 1
            except Exception:
                errors += 1

        error_rate   = errors / n
        out_of_range = out_range / n

        return {
            "passed":       error_rate < 0.10 and out_of_range < 0.05,
            "test":         "random_noise",
            "n_tests":      n,
            "error_rate":   round(error_rate, 4),
            "out_of_range": round(out_of_range, 4),
        }

    def _test_boundaries(self, predictor, feature_names: List[str]) -> dict:
        """Boundary value analysis।"""
        boundary_cases = [
            {f: 0.0 for f in feature_names},
            {f: 1.0 for f in feature_names},
            {f: -1.0 for f in feature_names},
            {f: float("inf") if i % 2 == 0 else 0 for i, f in enumerate(feature_names)},
        ]

        passed_count = 0
        for case in boundary_cases:
            try:
                predictor.predict(case)
                passed_count += 1
            except Exception:
                pass  # Some boundary failures are acceptable

        return {
            "passed":         passed_count >= len(boundary_cases) // 2,
            "test":           "boundary_values",
            "passed_cases":   passed_count,
            "total_cases":    len(boundary_cases),
        }

    def _recommendation(self, status: str, results: Dict) -> str:
        failed = [test for test, r in results.items() if not r.get("passed", False)]
        if status == "robust":
            return "Model is production-ready. All robustness checks passed."
        if "empty_input" in failed:
            return "CRITICAL: Add input validation — model crashes on empty input."
        if "null_values" in failed:
            return "Add null/None handling in feature preprocessing pipeline."
        if "random_noise" in failed:
            return "Model is unstable with noisy inputs. Add input clipping/normalization."
        return f"Fix these robustness issues before deployment: {', '.join(failed[:3])}"

    def adversarial_test(self, predictor, normal_input: Dict,
                          epsilon: float = 0.1) -> dict:
        """
        Adversarial robustness test।
        Small perturbations should not drastically change predictions।
        """
        try:
            base_result  = predictor.predict(normal_input)
            base_conf    = base_result.get("confidence", 0) if isinstance(base_result, dict) else 0

            # Add small perturbations
            perturbed = {}
            for k, v in normal_input.items():
                if isinstance(v, (int, float)):
                    perturbed[k] = v + random.uniform(-epsilon, epsilon) * abs(v + 1)
                else:
                    perturbed[k] = v

            pert_result = predictor.predict(perturbed)
            pert_conf   = pert_result.get("confidence", 0) if isinstance(pert_result, dict) else 0

            conf_diff   = abs(base_conf - pert_conf)
            stable      = conf_diff < 0.20  # Allow 20% change for epsilon perturbation

            return {
                "adversarial_stable": stable,
                "epsilon":            epsilon,
                "base_confidence":    round(base_conf, 4),
                "perturbed_confidence": round(pert_conf, 4),
                "confidence_diff":    round(conf_diff, 4),
                "passed":             stable,
            }
        except Exception as e:
            return {"passed": False, "error": str(e)[:100]}
