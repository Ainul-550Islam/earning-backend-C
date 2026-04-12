"""
api/ai_engine/TESTING_EVALUATION/bias_detection.py
===================================================
Bias Detection — AI model fairness ও bias testing।
Demographic parity, equalized odds, individual fairness।
GDPR Article 22 compliance এর জন্য।
Marketing platform এ fair pricing ও offer distribution নিশ্চিত।
"""

import logging
import math
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class BiasDetector:
    """
    AI model bias ও fairness evaluation।
    Multiple fairness metrics — demographic parity, equalized odds।
    """

    def detect(self, predictions: List, sensitive_groups: List,
               threshold: float = 0.10) -> dict:
        """
        Demographic parity bias detect করো।
        Different groups এর prediction rate compare করো।
        """
        if not predictions or not sensitive_groups:
            return {'bias_detected': False, 'reason': 'no_data'}
        if len(predictions) != len(sensitive_groups):
            return {'bias_detected': False, 'reason': 'length_mismatch'}

        # Group by sensitive attribute
        groups: Dict[str, List] = {}
        for pred, group in zip(predictions, sensitive_groups):
            groups.setdefault(str(group), []).append(float(pred))

        if len(groups) < 2:
            return {'bias_detected': False, 'reason': 'single_group'}

        # Group statistics
        group_stats = {}
        for g, vals in groups.items():
            n    = len(vals)
            mean = sum(vals) / n
            positive_rate = sum(1 for v in vals if v >= 0.5) / n
            group_stats[g] = {
                'count':         n,
                'mean':          round(mean, 4),
                'positive_rate': round(positive_rate, 4),
            }

        rates   = [s['positive_rate'] for s in group_stats.values()]
        max_disp = max(rates) - min(rates)
        most_favored   = max(group_stats, key=lambda g: group_stats[g]['positive_rate'])
        least_favored  = min(group_stats, key=lambda g: group_stats[g]['positive_rate'])

        bias_detected = max_disp > threshold

        return {
            'bias_detected':   bias_detected,
            'metric':          'demographic_parity',
            'max_disparity':   round(max_disp, 4),
            'threshold':       threshold,
            'group_stats':     group_stats,
            'most_favored':    most_favored,
            'least_favored':   least_favored,
            'severity':        self._severity(max_disp, threshold),
            'recommendation':  self._recommend(bias_detected, max_disp),
        }

    def _severity(self, disparity: float, threshold: float) -> str:
        ratio = disparity / max(threshold, 0.001)
        if ratio >= 3.0:  return 'critical'
        if ratio >= 2.0:  return 'high'
        if ratio >= 1.0:  return 'medium'
        return 'low'

    def _recommend(self, bias: bool, disparity: float) -> str:
        if not bias:
            return 'No action needed — model is fair.'
        if disparity >= 0.20:
            return 'CRITICAL: Retrain with balanced data and fairness constraints immediately.'
        return 'Retrain with balanced dataset. Apply fairness-aware training techniques.'

    def equalized_odds(self, y_true: List, y_pred: List,
                        sensitive_groups: List, threshold: float = 0.10) -> dict:
        """
        Equalized Odds check করো।
        TPR ও FPR সব groups এর জন্য similar হওয়া উচিত।
        """
        if len(y_true) != len(y_pred) != len(sensitive_groups):
            return {'error': 'length_mismatch'}

        group_metrics: Dict[str, Dict] = {}
        groups = set(str(g) for g in sensitive_groups)

        for group in groups:
            idxs = [i for i, g in enumerate(sensitive_groups) if str(g) == group]
            gt   = [y_true[i] for i in idxs]
            gp   = [y_pred[i] for i in idxs]

            tp = sum(1 for t, p in zip(gt, gp) if t == 1 and p == 1)
            fp = sum(1 for t, p in zip(gt, gp) if t == 0 and p == 1)
            tn = sum(1 for t, p in zip(gt, gp) if t == 0 and p == 0)
            fn = sum(1 for t, p in zip(gt, gp) if t == 1 and p == 0)

            tpr = tp / max(tp + fn, 1)
            fpr = fp / max(fp + tn, 1)

            group_metrics[group] = {
                'tpr': round(tpr, 4),
                'fpr': round(fpr, 4),
                'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
                'count': len(idxs),
            }

        tpr_values = [m['tpr'] for m in group_metrics.values()]
        fpr_values = [m['fpr'] for m in group_metrics.values()]
        tpr_disp   = max(tpr_values) - min(tpr_values)
        fpr_disp   = max(fpr_values) - min(fpr_values)

        return {
            'metric':           'equalized_odds',
            'tpr_disparity':    round(tpr_disp, 4),
            'fpr_disparity':    round(fpr_disp, 4),
            'tpr_fair':         tpr_disp <= threshold,
            'fpr_fair':         fpr_disp <= threshold,
            'fully_fair':       tpr_disp <= threshold and fpr_disp <= threshold,
            'group_metrics':    group_metrics,
            'threshold':        threshold,
        }

    def individual_fairness(self, embeddings: List[List[float]],
                             predictions: List[float],
                             top_k: int = 5) -> dict:
        """
        Individual Fairness — similar individuals একই prediction পাচ্ছে কিনা।
        Similar input → similar output।
        """
        if not embeddings or len(embeddings) != len(predictions):
            return {'error': 'invalid_input'}

        try:
            violations = []
            n = min(len(embeddings), 100)  # Sample first 100 for efficiency

            for i in range(n):
                # Find top-k similar individuals
                sims = []
                for j in range(n):
                    if i == j:
                        continue
                    sim = self._cosine_sim(embeddings[i], embeddings[j])
                    sims.append((j, sim))

                top_similar = sorted(sims, key=lambda x: x[1], reverse=True)[:top_k]

                for j, sim in top_similar:
                    if sim > 0.90:  # Very similar
                        pred_diff = abs(predictions[i] - predictions[j])
                        if pred_diff > 0.20:  # But very different prediction
                            violations.append({
                                'individual_a': i,
                                'individual_b': j,
                                'similarity':   round(sim, 4),
                                'pred_diff':    round(pred_diff, 4),
                            })

            return {
                'metric':          'individual_fairness',
                'violations':      len(violations),
                'sample_size':     n,
                'violation_rate':  round(len(violations) / max(n * top_k, 1), 4),
                'is_fair':         len(violations) == 0,
                'top_violations':  violations[:5],
            }
        except Exception as e:
            return {'error': str(e)}

    def _cosine_sim(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot  = sum(x * y for x, y in zip(a, b))
        na   = math.sqrt(sum(x**2 for x in a))
        nb   = math.sqrt(sum(y**2 for y in b))
        return dot / (na * nb) if na and nb else 0.0

    def representation_bias(self, dataset_groups: Dict[str, int],
                              population_groups: Dict[str, float]) -> dict:
        """
        Dataset এ group representation check করো।
        Training data population এর representative কিনা।
        """
        total_dataset = sum(dataset_groups.values())
        results = {}

        for group in population_groups:
            pop_pct  = population_groups[group]
            data_pct = dataset_groups.get(group, 0) / max(total_dataset, 1)
            gap      = data_pct - pop_pct
            results[group] = {
                'dataset_pct':    round(data_pct, 4),
                'population_pct': round(pop_pct, 4),
                'gap':            round(gap, 4),
                'underrepresented': gap < -0.05,
                'overrepresented':  gap > 0.05,
            }

        under = [g for g, v in results.items() if v['underrepresented']]
        over  = [g for g, v in results.items() if v['overrepresented']]

        return {
            'metric':               'representation_bias',
            'group_analysis':       results,
            'underrepresented':     under,
            'overrepresented':      over,
            'is_representative':    not under and not over,
            'recommendation':       f"Collect more data for: {', '.join(under)}" if under else 'Dataset is representative.',
        }

    def run_full_bias_audit(self, model_id: str, audit_data: dict) -> dict:
        """Complete bias audit for a deployed model।"""
        results = {
            'model_id':    model_id,
            'audit_date':  str(__import__('django.utils.timezone', fromlist=['timezone']).timezone.now()),
            'tests_run':   [],
            'overall_fair': True,
        }

        preds  = audit_data.get('predictions', [])
        groups = audit_data.get('sensitive_groups', [])
        y_true = audit_data.get('ground_truth', [])

        if preds and groups:
            demo = self.detect(preds, groups)
            results['demographic_parity'] = demo
            results['tests_run'].append('demographic_parity')
            if demo.get('bias_detected'):
                results['overall_fair'] = False

        if preds and groups and y_true:
            y_bin = [1 if p >= 0.5 else 0 for p in preds]
            eq_odds = self.equalized_odds(y_true, y_bin, groups)
            results['equalized_odds'] = eq_odds
            results['tests_run'].append('equalized_odds')
            if not eq_odds.get('fully_fair'):
                results['overall_fair'] = False

        results['verdict'] = 'FAIR' if results['overall_fair'] else 'BIASED — ACTION REQUIRED'
        return results
