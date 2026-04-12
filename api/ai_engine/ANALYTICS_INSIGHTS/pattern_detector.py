"""
api/ai_engine/ANALYTICS_INSIGHTS/pattern_detector.py
=====================================================
Pattern Detector — recurring patterns in data。
"""

import logging
from typing import List, Dict
logger = logging.getLogger(__name__)


class PatternDetector:
    def detect_weekly_pattern(self, daily_values: List[float]) -> dict:
        if len(daily_values) < 7:
            return {'pattern': 'insufficient_data'}
        week_avg = [sum(daily_values[i::7]) / max(len(daily_values[i::7]), 1) for i in range(7)]
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        overall_avg = sum(week_avg) / len(week_avg)
        patterns = {
            days[i]: {
                'avg': round(week_avg[i], 2),
                'relative': round(week_avg[i] / max(overall_avg, 0.001), 3),
            }
            for i in range(7)
        }
        peak_day = days[week_avg.index(max(week_avg))]
        return {'pattern': patterns, 'peak_day': peak_day, 'overall_avg': round(overall_avg, 2)}

    def detect_growth_pattern(self, values: List[float]) -> str:
        if len(values) < 3:
            return 'unknown'
        diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
        avg_diff = sum(diffs) / len(diffs)
        if avg_diff > 0:  return 'growing'
        if avg_diff < 0:  return 'declining'
        return 'stable'


"""
api/ai_engine/ANALYTICS_INSIGHTS/correlation_analyzer.py
=========================================================
Correlation Analyzer。
"""


class CorrelationAnalyzer:
    def correlate(self, data: Dict[str, List[float]]) -> dict:
        try:
            import numpy as np
            keys = list(data.keys())
            if len(keys) < 2:
                return {}
            matrix = {}
            for k1 in keys:
                for k2 in keys:
                    if k1 >= k2:
                        continue
                    v1, v2 = data[k1], data[k2]
                    min_len = min(len(v1), len(v2))
                    if min_len < 2:
                        continue
                    corr = float(np.corrcoef(v1[:min_len], v2[:min_len])[0, 1])
                    matrix[f"{k1}_vs_{k2}"] = round(corr, 4)
            return matrix
        except Exception as e:
            return {'error': str(e)}


"""
api/ai_engine/ANALYTICS_INSIGHTS/causal_inference.py
=====================================================
Causal Inference — A/B test causal analysis。
"""


class CausalInference:
    def estimate_ate(self, treatment_outcomes: List[float],
                     control_outcomes: List[float]) -> dict:
        """Average Treatment Effect estimation。"""
        if not treatment_outcomes or not control_outcomes:
            return {'ate': 0.0, 'significant': False}
        t_mean = sum(treatment_outcomes) / len(treatment_outcomes)
        c_mean = sum(control_outcomes) / len(control_outcomes)
        ate    = t_mean - c_mean
        return {
            'ate':         round(ate, 4),
            'treatment_mean': round(t_mean, 4),
            'control_mean':   round(c_mean, 4),
            'relative_lift':  round((ate / max(abs(c_mean), 0.001)) * 100, 2),
            'significant':    abs(ate) > 0.05,
        }


"""
api/ai_engine/ANALYTICS_INSIGHTS/funnel_analyzer.py
====================================================
Funnel Analyzer — conversion funnel analysis。
"""


class FunnelAnalyzer:
    def analyze(self, funnel_steps: Dict[str, int]) -> dict:
        steps = list(funnel_steps.items())
        if not steps:
            return {}
        top_of_funnel = steps[0][1]
        results = {}
        for i, (step, count) in enumerate(steps):
            from_top  = round(count / max(top_of_funnel, 1), 4)
            from_prev = round(count / max(steps[i-1][1], 1), 4) if i > 0 else 1.0
            results[step] = {
                'count':       count,
                'from_top':    from_top,
                'from_prev':   from_prev,
                'drop_off_pct': round((1 - from_prev) * 100, 2) if i > 0 else 0.0,
            }
        bottleneck = min(results, key=lambda s: results[s]['from_prev'] if results[s]['from_prev'] < 1 else 1)
        return {'steps': results, 'bottleneck': bottleneck, 'overall_cvr': round(steps[-1][1] / max(top_of_funnel, 1), 4)}


"""
api/ai_engine/ANALYTICS_INSIGHTS/segmentation_analyzer.py
==========================================================
Segmentation Analyzer — segment performance comparison。
"""


class SegmentationAnalyzer:
    def compare_segments(self, segments: Dict[str, List[float]]) -> dict:
        results = {}
        for seg_name, values in segments.items():
            if not values:
                continue
            results[seg_name] = {
                'count': len(values),
                'mean':  round(sum(values) / len(values), 4),
                'min':   round(min(values), 4),
                'max':   round(max(values), 4),
            }
        if results:
            best = max(results, key=lambda s: results[s]['mean'])
            return {'segments': results, 'best_segment': best}
        return {}


"""
api/ai_engine/ANALYTICS_INSIGHTS/predictive_analytics.py
=========================================================
Predictive Analytics — forward-looking insights。
"""


class PredictiveAnalytics:
    def predict_metric(self, historical: List[float], periods: int = 7) -> dict:
        if not historical:
            return {'forecast': []}
        from ..ANALYTICS_INSIGHTS.trend_analyzer import TrendAnalyzer
        trend = TrendAnalyzer().analyze(historical)
        avg   = sum(historical[-7:]) / min(7, len(historical))
        pct   = trend.get('pct_change', 0) / 100
        forecast = [round(avg * (1 + pct * (i + 1) / periods), 2) for i in range(periods)]
        return {'forecast': forecast, 'trend': trend.get('trend', 'stable'), 'confidence': 0.65}


"""
api/ai_engine/ANALYTICS_INSIGHTS/prescriptive_analytics.py
===========================================================
Prescriptive Analytics — recommended actions for outcomes。
"""


class PrescriptiveAnalytics:
    def recommend_actions(self, current_metrics: dict, target_metrics: dict) -> List[dict]:
        actions = []
        for metric, target in target_metrics.items():
            current = current_metrics.get(metric, 0)
            gap     = target - current
            if abs(gap) < 0.01:
                continue
            direction = 'increase' if gap > 0 else 'decrease'
            actions.append({
                'metric':    metric,
                'current':   current,
                'target':    target,
                'gap':       round(gap, 4),
                'action':    f"{direction}_{metric}",
                'priority':  'high' if abs(gap / max(abs(target), 0.001)) > 0.2 else 'medium',
            })
        return sorted(actions, key=lambda x: x['priority'])


"""
api/ai_engine/ANALYTICS_INSIGHTS/diagnostic_analytics.py
=========================================================
Diagnostic Analytics — why did metric change?
"""


class DiagnosticAnalytics:
    def diagnose(self, metric_name: str, before: float, after: float,
                 factors: Dict[str, float]) -> dict:
        change = after - before
        contributions = {}
        total_factor_change = sum(abs(v) for v in factors.values()) or 1
        for factor, value in factors.items():
            contribution = round((abs(value) / total_factor_change) * change, 4)
            contributions[factor] = contribution

        top_factor = max(contributions, key=lambda k: abs(contributions[k])) if contributions else 'unknown'
        return {
            'metric':       metric_name,
            'change':       round(change, 4),
            'direction':    'increase' if change > 0 else 'decrease',
            'top_driver':   top_factor,
            'contributions': contributions,
        }
