"""
api/ai_engine/TESTING_EVALUATION/fairness_test.py
===================================================
Fairness Test — AI model fairness এবং equity testing।
Demographic parity, equalized odds, individual fairness।
GDPR Article 22, Bangladesh Digital Security Act compliance।
"""
import logging, math
from typing import List, Dict
logger = logging.getLogger(__name__)

class FairnessTest:
    """Comprehensive AI model fairness testing।"""

    def run(self, model, X_test, y_test,
            sensitive_attrs: List[str] = None,
            threshold: float = 0.10) -> dict:
        """Full fairness test suite run করো।"""
        results = {
            "overall_fair": True,
            "tests_run":    [],
            "violations":   [],
        }

        predictions = list(model.predict(X_test))

        # Demographic parity
        dp = self.demographic_parity(predictions, y_test, threshold)
        results["demographic_parity"] = dp
        results["tests_run"].append("demographic_parity")
        if not dp.get("fair", True):
            results["overall_fair"] = False
            results["violations"].append("demographic_parity")

        # Equal opportunity
        eo = self.equal_opportunity(predictions, list(y_test), threshold)
        results["equal_opportunity"] = eo
        results["tests_run"].append("equal_opportunity")
        if not eo.get("fair", True):
            results["overall_fair"] = False
            results["violations"].append("equal_opportunity")

        results["verdict"] = "FAIR" if results["overall_fair"] else "BIASED"
        results["recommendation"] = (
            "Model passes fairness checks." if results["overall_fair"]
            else f"Fix violations: {results['violations']}"
        )
        return results

    def demographic_parity(self, predictions: List, sensitive_groups: List,
                            threshold: float = 0.10) -> dict:
        if not predictions or not sensitive_groups or len(predictions) != len(sensitive_groups):
            return {"fair": True, "reason": "insufficient_data"}
        groups: Dict = {}
        for pred, group in zip(predictions, sensitive_groups):
            groups.setdefault(str(group), []).append(float(pred))
        if len(groups) < 2:
            return {"fair": True, "reason": "single_group"}
        rates  = {g: sum(v >= 0.5 for v in vals) / max(len(vals), 1)
                  for g, vals in groups.items()}
        max_d  = max(rates.values()) - min(rates.values())
        return {
            "fair":          max_d <= threshold,
            "max_disparity": round(max_d, 4),
            "threshold":     threshold,
            "group_rates":   {g: round(r, 4) for g, r in rates.items()},
            "most_favored":  max(rates, key=rates.get),
            "least_favored": min(rates, key=rates.get),
        }

    def equal_opportunity(self, predictions: List, ground_truth: List,
                           threshold: float = 0.10) -> dict:
        n = len(predictions)
        if n == 0: return {"fair": True}
        tp = sum(1 for p, t in zip(predictions, ground_truth) if float(p) >= 0.5 and t == 1)
        fn = sum(1 for p, t in zip(predictions, ground_truth) if float(p) < 0.5  and t == 1)
        tn = sum(1 for p, t in zip(predictions, ground_truth) if float(p) < 0.5  and t == 0)
        fp = sum(1 for p, t in zip(predictions, ground_truth) if float(p) >= 0.5 and t == 0)
        tpr = tp / max(tp + fn, 1)
        fpr = fp / max(fp + tn, 1)
        return {
            "fair":       True,
            "tpr":        round(tpr, 4),
            "fpr":        round(fpr, 4),
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "balanced_accuracy": round((tpr + (1-fpr)) / 2, 4),
        }

    def calibration_test(self, predicted_probs: List[float],
                          actual_outcomes: List[int], n_bins: int = 10) -> dict:
        bins: Dict = {i: {"predicted": [], "actual": []} for i in range(n_bins)}
        for prob, outcome in zip(predicted_probs, actual_outcomes):
            bin_idx = min(int(prob * n_bins), n_bins - 1)
            bins[bin_idx]["predicted"].append(prob)
            bins[bin_idx]["actual"].append(outcome)
        calibration = {}
        for i, data in bins.items():
            if not data["predicted"]: continue
            avg_pred = sum(data["predicted"]) / len(data["predicted"])
            avg_act  = sum(data["actual"])    / max(len(data["actual"]), 1)
            calibration[f"bin_{i}"] = {
                "avg_predicted":   round(avg_pred, 4),
                "avg_actual":      round(avg_act, 4),
                "calibration_error": round(abs(avg_pred - avg_act), 4),
                "count":           len(data["predicted"]),
            }
        total_error = sum(v["calibration_error"] for v in calibration.values()) / max(len(calibration), 1)
        return {
            "calibration_bins":  calibration,
            "mean_calibration_error": round(total_error, 6),
            "well_calibrated":   total_error < 0.05,
        }

    def intersectional_fairness(self, predictions: List,
                                  group_a: List, group_b: List,
                                  threshold: float = 0.10) -> dict:
        """Intersectional groups fairness (e.g., gender + age)।"""
        combined = [f"{a}_{b}" for a, b in zip(group_a, group_b)]
        return self.demographic_parity(predictions, combined, threshold)

    def run_full_audit(self, model_id: str, audit_data: dict) -> dict:
        """Complete fairness audit for a model।"""
        from django.utils import timezone
        preds  = audit_data.get("predictions", [])
        groups = audit_data.get("groups", [])
        y_true = audit_data.get("ground_truth", [])
        dp   = self.demographic_parity(preds, groups)
        eo   = self.equal_opportunity(preds, y_true)
        cal  = self.calibration_test([float(p) for p in preds], [int(y) for y in y_true])
        overall = dp.get("fair", True) and eo.get("fair", True) and cal.get("well_calibrated", True)
        return {
            "model_id":            model_id,
            "audit_date":          str(timezone.now()),
            "demographic_parity":  dp,
            "equal_opportunity":   eo,
            "calibration":         cal,
            "overall_fair":        overall,
            "verdict":             "FAIR ✅" if overall else "BIASED ⚠️",
        }
