"""
api/ai_engine/ANALYTICS_INSIGHTS/causal_inference.py
=====================================================
Causal Inference — কোন intervention কোন outcome cause করছে।
A/B test analysis, campaign impact measurement, feature attribution।
Marketing ও business decisions এর জন্য।
"""

import logging
import math
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CausalInference:
    """
    Causal inference engine।
    ATE, ATT, CATE estimation।
    Difference-in-Differences, Propensity Score Matching।
    """

    def estimate_ate(
        self,
        treatment_outcomes: List[float],
        control_outcomes: List[float],
        confidence: float = 0.95,
    ) -> dict:
        """
        Average Treatment Effect (ATE) estimation।
        Treatment group vs Control group outcome comparison।
        """
        if not treatment_outcomes or not control_outcomes:
            return {'ate': 0.0, 'significant': False, 'error': 'Insufficient data'}

        t_n    = len(treatment_outcomes)
        c_n    = len(control_outcomes)
        t_mean = sum(treatment_outcomes) / t_n
        c_mean = sum(control_outcomes) / c_n
        ate    = t_mean - c_mean

        # Variance
        t_var = sum((x - t_mean)**2 for x in treatment_outcomes) / max(t_n - 1, 1)
        c_var = sum((x - c_mean)**2 for x in control_outcomes) / max(c_n - 1, 1)
        se    = math.sqrt(t_var / t_n + c_var / c_n) or 0.001

        t_stat  = ate / se
        p_value = self._two_tailed_p(abs(t_stat))

        alpha   = 1 - confidence
        z_crit  = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.96)
        ci_low  = round(ate - z_crit * se, 6)
        ci_high = round(ate + z_crit * se, 6)

        return {
            'ate':             round(ate, 6),
            'treatment_mean':  round(t_mean, 6),
            'control_mean':    round(c_mean, 6),
            'relative_lift':   round((ate / max(abs(c_mean), 0.001)) * 100, 2),
            'se':              round(se, 6),
            't_statistic':     round(t_stat, 4),
            'p_value':         round(p_value, 6),
            'significant':     p_value < alpha,
            'confidence_interval': [ci_low, ci_high],
            'confidence_level': confidence,
            'sample_sizes':    {'treatment': t_n, 'control': c_n},
        }

    def _two_tailed_p(self, z: float) -> float:
        """Approximate two-tailed p-value from z-score।"""
        # Abramowitz and Stegun approximation
        t = 1 / (1 + 0.2316419 * abs(z))
        poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
        phi  = 1 - (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z**2) * poly
        return round(2 * (1 - phi), 6)

    def difference_in_differences(
        self,
        treatment_before: float,
        treatment_after: float,
        control_before: float,
        control_after: float,
    ) -> dict:
        """
        Difference-in-Differences (DiD) estimator।
        Time ও treatment দুটো dimension handle করে।
        Campaign/intervention impact measurement।
        """
        did = (treatment_after - treatment_before) - (control_after - control_before)
        treatment_change = treatment_after - treatment_before
        control_change   = control_after - control_before

        return {
            'did_estimate':     round(did, 6),
            'treatment_change': round(treatment_change, 6),
            'control_change':   round(control_change, 6),
            'interpretation':   f"Treatment caused {did:+.4f} additional change beyond natural trend.",
            'positive_impact':  did > 0,
        }

    def propensity_score_matching(
        self,
        treated_units: List[Dict],
        control_units: List[Dict],
        covariates: List[str],
    ) -> dict:
        """
        Propensity Score Matching (PSM)।
        Observational study এ confounding control করো।
        """
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
            import numpy as np

            all_units = treated_units + control_units
            X = np.array([[u.get(c, 0) for c in covariates] for u in all_units])
            y = np.array([1] * len(treated_units) + [0] * len(control_units))

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            lr = LogisticRegression(random_state=42)
            lr.fit(X_scaled, y)
            propensity_scores = lr.predict_proba(X_scaled)[:, 1]

            t_scores = propensity_scores[:len(treated_units)]
            c_scores = propensity_scores[len(treated_units):]

            return {
                'method':              'propensity_score_matching',
                'treated_count':       len(treated_units),
                'control_count':       len(control_units),
                'avg_treated_propensity': round(float(t_scores.mean()), 4),
                'avg_control_propensity': round(float(c_scores.mean()), 4),
                'balance_achieved':    abs(t_scores.mean() - c_scores.mean()) < 0.05,
                'covariates_used':     covariates,
            }
        except ImportError:
            return {'error': 'sklearn required for PSM', 'method': 'propensity_score_matching'}
        except Exception as e:
            return {'error': str(e)}

    def measure_campaign_impact(
        self,
        before_metrics: Dict[str, float],
        after_metrics: Dict[str, float],
        control_metrics: Optional[Dict[str, float]] = None,
    ) -> dict:
        """Marketing campaign এর causal impact measure করো।"""
        results = {}
        for metric in before_metrics:
            if metric not in after_metrics:
                continue
            before = before_metrics[metric]
            after  = after_metrics[metric]
            raw_change = after - before
            pct_change = (raw_change / max(abs(before), 0.001)) * 100

            did = None
            if control_metrics and metric in control_metrics:
                control_change = control_metrics[metric] - before
                did = raw_change - control_change

            results[metric] = {
                'before':     before,
                'after':      after,
                'raw_change': round(raw_change, 4),
                'pct_change': round(pct_change, 2),
                'did_estimate': round(did, 4) if did is not None else None,
                'direction':  'improved' if raw_change > 0 else 'declined',
            }

        return {
            'metrics':      results,
            'overall_positive': sum(1 for v in results.values() if v['direction'] == 'improved'),
            'overall_negative': sum(1 for v in results.values() if v['direction'] == 'declined'),
        }
