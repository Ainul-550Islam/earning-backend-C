"""
api/ai_engine/OPTIMIZATION_ENGINES/a_b_test_optimizer.py
=========================================================
A/B Test Optimizer — statistical significance calculation।
"""

import math
import logging

logger = logging.getLogger(__name__)


class ABTestOptimizer:
    """A/B test statistical analysis।"""

    def analyze(self, control_conversions: int, control_visitors: int,
                treatment_conversions: int, treatment_visitors: int) -> dict:
        if control_visitors == 0 or treatment_visitors == 0:
            return {'significant': False, 'winner': 'pending', 'confidence': 0.0}

        cr_control   = control_conversions / control_visitors
        cr_treatment = treatment_conversions / treatment_visitors
        lift         = ((cr_treatment - cr_control) / cr_control * 100) if cr_control > 0 else 0

        # Z-test
        p_pool = (control_conversions + treatment_conversions) / (control_visitors + treatment_visitors)
        se = math.sqrt(p_pool * (1 - p_pool) * (1/control_visitors + 1/treatment_visitors))
        z_score = (cr_treatment - cr_control) / se if se > 0 else 0

        confidence = self._z_to_confidence(abs(z_score))
        significant = confidence >= 0.95

        if significant:
            winner = 'treatment' if cr_treatment > cr_control else 'control'
        else:
            winner = 'pending'

        return {
            'significant':       significant,
            'winner':            winner,
            'confidence':        round(confidence, 4),
            'lift_pct':          round(lift, 2),
            'cr_control':        round(cr_control, 4),
            'cr_treatment':      round(cr_treatment, 4),
            'z_score':           round(z_score, 4),
            'sample_size_ok':    control_visitors >= 1000 and treatment_visitors >= 1000,
        }

    def _z_to_confidence(self, z: float) -> float:
        """Z-score থেকে approximate confidence level।"""
        if z >= 2.576: return 0.99
        if z >= 1.960: return 0.975
        if z >= 1.645: return 0.95
        if z >= 1.282: return 0.90
        return min(0.89, 0.50 + z * 0.15)
