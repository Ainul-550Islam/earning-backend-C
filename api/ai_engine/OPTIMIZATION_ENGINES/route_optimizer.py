"""
api/ai_engine/OPTIMIZATION_ENGINES/route_optimizer.py
======================================================
Route Optimizer — user journey ও funnel path optimization।
Onboarding flow, offer completion journey, withdrawal path optimize করো।
Drop-off point detection ও fix suggestions।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """
    User journey/funnel route optimization।
    Shortest path to conversion with minimum friction।
    """

    def optimize_journey(self, journey_steps: List[Dict]) -> dict:
        """User journey analyze ও optimize করো।"""
        if not journey_steps:
            return {'optimized': False, 'reason': 'No journey data'}

        total      = len(journey_steps)
        completed  = sum(1 for s in journey_steps if s.get('completed', False))
        drop_offs  = [s for s in journey_steps if not s.get('completed', False)]
        completion = round(completed / total, 4) if total > 0 else 0

        bottlenecks = self._find_bottlenecks(journey_steps)
        optimized   = self._suggest_optimizations(bottlenecks, journey_steps)

        return {
            'total_steps':      total,
            'completed_steps':  completed,
            'completion_rate':  completion,
            'drop_off_count':   len(drop_offs),
            'drop_off_steps':   [s.get('step_name', f'step_{i}') for i, s in enumerate(drop_offs)],
            'bottlenecks':      bottlenecks,
            'optimizations':    optimized,
            'estimated_lift':   f"{len(bottlenecks) * 5}% completion rate improvement possible",
        }

    def _find_bottlenecks(self, steps: List[Dict]) -> List[Dict]:
        bottlenecks = []
        for i, step in enumerate(steps):
            drop_rate = step.get('drop_rate', 0)
            avg_time  = step.get('avg_time_seconds', 0)
            if drop_rate >= 0.30:
                bottlenecks.append({
                    'step':        step.get('step_name', f'step_{i+1}'),
                    'drop_rate':   round(drop_rate, 4),
                    'avg_time_s':  avg_time,
                    'severity':    'critical' if drop_rate >= 0.50 else 'high' if drop_rate >= 0.30 else 'medium',
                })
        return sorted(bottlenecks, key=lambda x: x['drop_rate'], reverse=True)

    def _suggest_optimizations(self, bottlenecks: List[Dict], steps: List[Dict]) -> List[Dict]:
        suggestions = []
        for b in bottlenecks:
            step_name = b['step']
            drop_rate = b['drop_rate']
            avg_time  = b['avg_time_s']

            if 'payment' in step_name.lower() or 'kyc' in step_name.lower():
                suggestions.append({'step': step_name, 'action': 'Simplify form — reduce required fields', 'priority': 'urgent'})
            elif avg_time > 120:
                suggestions.append({'step': step_name, 'action': 'Break into smaller sub-steps', 'priority': 'high'})
            elif drop_rate >= 0.50:
                suggestions.append({'step': step_name, 'action': 'Add progress indicator and incentive', 'priority': 'high'})
            else:
                suggestions.append({'step': step_name, 'action': 'A/B test alternative UI/copy', 'priority': 'medium'})
        return suggestions

    def optimize_onboarding(self, user_type: str = 'new') -> dict:
        """Onboarding flow optimization।"""
        flows = {
            'new': [
                {'step': 'register', 'est_seconds': 60, 'can_skip': False},
                {'step': 'verify_email', 'est_seconds': 30, 'can_skip': False},
                {'step': 'setup_profile', 'est_seconds': 120, 'can_skip': True},
                {'step': 'first_offer', 'est_seconds': 300, 'can_skip': False},
                {'step': 'earn_first_coin', 'est_seconds': 10, 'can_skip': False},
            ],
            'returning': [
                {'step': 'login', 'est_seconds': 15, 'can_skip': False},
                {'step': 'show_new_offers', 'est_seconds': 30, 'can_skip': True},
            ],
        }
        flow = flows.get(user_type, flows['new'])
        total_time = sum(s['est_seconds'] for s in flow if not s['can_skip'])
        return {
            'user_type':     user_type,
            'steps':         flow,
            'required_steps': sum(1 for s in flow if not s['can_skip']),
            'min_time_sec':  total_time,
            'recommendation': 'Progressive disclosure — show complexity gradually.',
        }

    def withdrawal_path_optimizer(self) -> dict:
        """Withdrawal journey friction points identify করো।"""
        friction_points = [
            {'step': 'check_balance', 'friction': 'low', 'fix': 'Show balance prominently'},
            {'step': 'select_method', 'friction': 'medium', 'fix': 'Remember last used method'},
            {'step': 'kyc_verification', 'friction': 'high', 'fix': 'One-time KYC, save for future'},
            {'step': 'enter_amount', 'friction': 'low', 'fix': 'Show quick-select amounts'},
            {'step': 'confirmation', 'friction': 'medium', 'fix': 'Single-tap confirm for repeat users'},
        ]
        return {
            'friction_points': friction_points,
            'high_friction_count': sum(1 for f in friction_points if f['friction'] == 'high'),
            'estimated_improvement': '25% faster withdrawal with all fixes applied',
        }
