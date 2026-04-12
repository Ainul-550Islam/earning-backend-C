"""
api/ai_engine/ANALYTICS_INSIGHTS/funnel_analyzer.py
====================================================
Funnel Analyzer — conversion funnel analysis ও optimization।
Registration → Verification → First Offer → Earn → Withdraw funnel।
Drop-off detection, bottleneck identification, A/B test recommendations।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class FunnelAnalyzer:
    """
    Multi-step conversion funnel analyzer।
    Earning platform এর core user journey।
    """

    # Standard earning app funnel
    STANDARD_FUNNEL = [
        'registration',
        'email_verification',
        'profile_completion',
        'first_offer_view',
        'first_offer_click',
        'first_offer_complete',
        'first_coin_earn',
        'first_withdrawal',
    ]

    def analyze(self, funnel_steps: Dict[str, int],
                 total_entered: int = None) -> dict:
        """
        Funnel conversion analyze করো।
        funnel_steps: {'registration': 10000, 'verification': 7500, ...}
        """
        if not funnel_steps:
            return {'error': 'No funnel data'}

        steps    = list(funnel_steps.items())
        top_count = total_entered or steps[0][1]

        results = {}
        for i, (step, count) in enumerate(steps):
            from_top  = round(count / max(top_count, 1), 4)
            from_prev = round(count / max(steps[i-1][1], 1), 4) if i > 0 else 1.0
            drop_pct  = round((1 - from_prev) * 100, 2) if i > 0 else 0.0

            results[step] = {
                'count':       count,
                'from_top':    from_top,
                'from_prev':   from_prev,
                'drop_off_pct': drop_pct,
                'health':      self._step_health(from_prev, step),
            }

        # Bottleneck = biggest drop-off
        if len(steps) > 1:
            bottleneck = min(
                ((s, results[s]) for s in results if results[s]['from_prev'] < 1.0),
                key=lambda x: x[1]['from_prev'],
                default=(None, {})
            )
        else:
            bottleneck = (None, {})

        overall_cvr = round(steps[-1][1] / max(top_count, 1), 4)

        return {
            'steps':            results,
            'overall_cvr':      overall_cvr,
            'total_entered':    top_count,
            'total_converted':  steps[-1][1],
            'bottleneck':       bottleneck[0],
            'bottleneck_drop':  round(bottleneck[1].get('drop_off_pct', 0), 2),
            'optimization_opportunity': self._opportunity(results, bottleneck),
            'recommendations':  self._recommendations(results),
        }

    def _step_health(self, from_prev: float, step: str) -> str:
        """Step health classify করো।"""
        benchmarks = {
            'email_verification':   0.70,
            'profile_completion':   0.60,
            'first_offer_click':    0.50,
            'first_offer_complete': 0.40,
            'first_withdrawal':     0.30,
        }
        threshold = benchmarks.get(step, 0.60)
        if from_prev >= threshold * 1.20:  return 'excellent'
        if from_prev >= threshold:          return 'good'
        if from_prev >= threshold * 0.70:  return 'needs_improvement'
        return 'critical'

    def _opportunity(self, results: Dict, bottleneck: tuple) -> str:
        """Biggest improvement opportunity।"""
        if not bottleneck[0]:
            return 'Funnel is performing well'
        step = bottleneck[0]
        drop = bottleneck[1].get('drop_off_pct', 0)
        count = results.get(step, {}).get('count', 0)
        return (
            f"Fix '{step}' step — {drop:.1f}% users drop here. "
            f"Recovering 20% of drop-offs = +{round(count * 0.20):.0f} conversions."
        )

    def _recommendations(self, results: Dict) -> List[str]:
        """Step-specific recommendations।"""
        recommendations = []
        for step, data in results.items():
            health = data.get('health', 'good')
            if health == 'critical':
                recommendations.append(self._step_fix(step, data.get('drop_off_pct', 0)))
        return recommendations[:5]

    def _step_fix(self, step: str, drop_pct: float) -> str:
        fixes = {
            'email_verification':   f'Email verification {drop_pct:.0f}% drop — send reminder SMS + reduce expiry time',
            'profile_completion':   f'Profile {drop_pct:.0f}% drop — make optional fields optional, show completion benefits',
            'first_offer_view':     f'Offer view {drop_pct:.0f}% drop — improve offer listing UI and discovery',
            'first_offer_click':    f'Offer click {drop_pct:.0f}% drop — improve offer card design and reward visibility',
            'first_offer_complete': f'Completion {drop_pct:.0f}% drop — simplify requirements, show progress bar',
            'first_withdrawal':     f'Withdrawal {drop_pct:.0f}% drop — reduce minimum amount, add more payment methods',
        }
        return fixes.get(step, f"Step '{step}' has {drop_pct:.0f}% drop-off — investigate UX issues")

    def cohort_funnel(self, cohorts: Dict[str, Dict[str, int]]) -> dict:
        """Multiple cohorts এর funnel comparison।"""
        analyses = {}
        for cohort_name, funnel_data in cohorts.items():
            analyses[cohort_name] = self.analyze(funnel_data)

        # Find best and worst cohorts by overall CVR
        cvrs = {c: analyses[c].get('overall_cvr', 0) for c in analyses}
        best  = max(cvrs, key=cvrs.get) if cvrs else None
        worst = min(cvrs, key=cvrs.get) if cvrs else None

        return {
            'cohort_analyses':  analyses,
            'best_cohort':      best,
            'worst_cohort':     worst,
            'best_cvr':         cvrs.get(best, 0) if best else 0,
            'worst_cvr':        cvrs.get(worst, 0) if worst else 0,
        }

    def ab_test_funnel(self, control_funnel: Dict[str, int],
                        treatment_funnel: Dict[str, int]) -> dict:
        """Control vs Treatment funnel comparison।"""
        ctrl    = self.analyze(control_funnel)
        treat   = self.analyze(treatment_funnel)
        ctrl_cvr  = ctrl.get('overall_cvr', 0)
        treat_cvr = treat.get('overall_cvr', 0)
        lift      = (treat_cvr - ctrl_cvr) / max(ctrl_cvr, 0.001) * 100

        return {
            'control':   ctrl,
            'treatment': treat,
            'lift_pct':  round(lift, 2),
            'winner':    'treatment' if lift > 0 else 'control',
            'significant': abs(lift) >= 5,
        }

    def micro_funnel_analysis(self, page_events: List[Dict]) -> dict:
        """Page-level micro funnel (scroll, click, submit)।"""
        events_order = ['page_view', 'scroll_50', 'scroll_100', 'button_hover', 'button_click', 'form_submit', 'success']
        counts = {e: sum(1 for ev in page_events if ev.get('event') == e) for e in events_order}
        non_zero = {k: v for k, v in counts.items() if v > 0}
        return self.analyze(non_zero) if non_zero else {'error': 'No events'}
