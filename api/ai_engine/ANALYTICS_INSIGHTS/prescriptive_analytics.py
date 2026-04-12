"""
api/ai_engine/ANALYTICS_INSIGHTS/prescriptive_analytics.py
===========================================================
Prescriptive Analytics — what ACTION should be taken।
Data → Insight → Recommendation → Action।
Marketing automation, campaign decisions, pricing actions।
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class PrescriptiveAnalytics:
    """
    Prescriptive analytics — কী করতে হবে বলে দাও।
    Not just what happened or will happen — but what TO DO।
    """

    def recommend_actions(self, current: dict, target: dict,
                           constraints: dict = None) -> List[Dict]:
        """Current → Target gap এর জন্য concrete actions recommend করো।"""
        constraints = constraints or {}
        actions = []

        for metric, target_val in target.items():
            current_val = current.get(metric, 0)
            gap         = target_val - current_val
            if abs(gap) < 0.001:
                continue

            pct_gap  = (gap / max(abs(target_val), 0.001)) * 100
            priority = 'urgent' if abs(pct_gap) > 30 else 'high' if abs(pct_gap) > 15 else 'medium'

            action = self._action_for_metric(metric, gap, current_val, target_val)
            if action:
                actions.append({
                    'metric':          metric,
                    'current':         round(current_val, 4),
                    'target':          round(target_val, 4),
                    'gap':             round(gap, 4),
                    'gap_pct':         round(pct_gap, 2),
                    'priority':        priority,
                    'action':          action['action'],
                    'expected_impact': action['impact'],
                    'effort':          action['effort'],
                    'timeline':        action['timeline'],
                })

        return sorted(actions, key=lambda x: {'urgent': 0, 'high': 1, 'medium': 2}.get(x['priority'], 3))

    def _action_for_metric(self, metric: str, gap: float, current: float, target: float) -> dict:
        playbook = {
            'conversion_rate': {
                'action': 'A/B test CTA button color and copy' if gap > 0 else 'Review offer quality',
                'impact': '5-15% CVR improvement', 'effort': 'medium', 'timeline': '2 weeks'
            },
            'churn_rate': {
                'action': 'Launch 7-day re-engagement email sequence' if gap < 0 else 'Reduce friction in key flows',
                'impact': '10-20% churn reduction', 'effort': 'low', 'timeline': '1 week'
            },
            'revenue': {
                'action': 'Increase high-LTV user offer frequency' if gap > 0 else 'Review pricing model',
                'impact': '15-25% revenue lift', 'effort': 'medium', 'timeline': '2-4 weeks'
            },
            'dau': {
                'action': 'Push notification campaign for dormant users' if gap > 0 else 'Improve onboarding',
                'impact': '8-18% DAU increase', 'effort': 'low', 'timeline': '3 days'
            },
            'ltv': {
                'action': 'VIP program expansion + referral bonus increase',
                'impact': '20-30% LTV improvement', 'effort': 'high', 'timeline': '4-8 weeks'
            },
        }
        return playbook.get(metric, {
            'action': f"Investigate and address {metric} gap",
            'impact': f"Close {abs(gap):.2f} unit gap",
            'effort': 'unknown', 'timeline': 'TBD'
        })

    def campaign_decision(self, campaign_metrics: dict) -> dict:
        """Campaign keep/pause/scale/stop decision।"""
        roi        = campaign_metrics.get('roi', 0)
        ctr        = campaign_metrics.get('ctr', 0)
        cvr        = campaign_metrics.get('cvr', 0)
        spend      = campaign_metrics.get('spend', 0)
        budget_used = campaign_metrics.get('budget_used_pct', 0)

        if roi < -0.5 or (spend > 10000 and cvr < 0.01):
            decision = 'STOP'
            reason   = f'Negative ROI ({roi:.1%}) or extremely low CVR ({cvr:.2%})'
            action   = 'Stop campaign immediately. Review targeting and creative.'
        elif roi < 0:
            decision = 'PAUSE'
            reason   = f'Negative ROI ({roi:.1%})'
            action   = 'Pause and optimize. Test new creatives and audiences.'
        elif roi > 2.0 and budget_used < 0.70:
            decision = 'SCALE'
            reason   = f'Strong ROI ({roi:.1%}) with budget remaining'
            action   = f'Increase budget by 30-50%. Expand to similar audiences.'
        elif roi > 0.5:
            decision = 'MAINTAIN'
            reason   = f'Positive ROI ({roi:.1%})'
            action   = 'Keep running. Minor optimizations only.'
        else:
            decision = 'OPTIMIZE'
            reason   = f'Low ROI ({roi:.1%}) — needs improvement'
            action   = 'A/B test creatives. Refine targeting. Lower bids.'

        return {
            'decision':     decision,
            'reason':       reason,
            'action':       action,
            'metrics':      campaign_metrics,
            'auto_execute': decision in ('STOP', 'PAUSE'),
        }

    def pricing_recommendation(self, current_price: float, metrics: dict) -> dict:
        """Dynamic pricing recommendation।"""
        demand_score  = metrics.get('demand_score', 0.5)
        competition   = metrics.get('competition_index', 1.0)
        margin        = metrics.get('current_margin', 0.30)
        elasticity    = metrics.get('price_elasticity', -1.5)

        if demand_score > 0.80 and competition < 0.80:
            direction = 'increase'
            pct       = min(15, (demand_score - 0.50) * 20)
        elif margin < 0.10 or demand_score < 0.30:
            direction = 'decrease'
            pct       = min(20, (0.50 - demand_score) * 30)
        else:
            direction = 'maintain'
            pct       = 0

        new_price = round(current_price * (1 + pct / 100 * (1 if direction == 'increase' else -1)), 2)
        return {
            'current_price':   current_price,
            'recommended_price': new_price,
            'direction':       direction,
            'change_pct':      round(pct, 2),
            'demand_score':    demand_score,
            'reason':          f'{direction.capitalize()} price — demand={demand_score:.2f} competition={competition:.2f}',
        }
