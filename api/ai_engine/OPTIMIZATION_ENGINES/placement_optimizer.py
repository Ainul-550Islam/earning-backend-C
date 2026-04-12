"""
api/ai_engine/OPTIMIZATION_ENGINES/placement_optimizer.py
==========================================================
Placement Optimizer — offer/ad position optimization।
Which offer to show at which position for max engagement।
CTR, conversion, revenue per position optimize করো।
"""

import logging
import math
from typing import List, Dict

logger = logging.getLogger(__name__)


class PlacementOptimizer:
    """
    Optimal placement/position allocation।
    Position-based CTR decay model।
    """

    # Position CTR decay coefficients (empirically derived)
    POSITION_CTR_WEIGHTS = {
        1: 1.000, 2: 0.850, 3: 0.720, 4: 0.600,
        5: 0.500, 6: 0.400, 7: 0.320, 8: 0.260,
        9: 0.210, 10: 0.170,
    }

    def optimize(self, items: List[Dict], positions: int = 10,
                 optimize_for: str = 'revenue') -> List[Dict]:
        """
        Items কে positions এ optimally assign করো।
        optimize_for: 'ctr' | 'revenue' | 'conversion' | 'engagement'
        """
        if not items:
            return []

        # Score by objective
        scored = self._score_items(items, optimize_for)
        sorted_items = sorted(scored, key=lambda x: x['objective_score'], reverse=True)

        result = []
        for pos in range(1, min(positions + 1, len(sorted_items) + 1)):
            item = sorted_items[pos - 1].copy()
            pos_weight  = self.POSITION_CTR_WEIGHTS.get(pos, max(0.1, 1.0 / pos))
            expected_ctr = round(item.get('base_ctr', 0.08) * pos_weight, 4)
            expected_rev = round(expected_ctr * float(item.get('reward', 100)), 2)

            item.update({
                'position':          pos,
                'position_weight':   pos_weight,
                'expected_ctr':      expected_ctr,
                'expected_revenue':  expected_rev,
            })
            result.append(item)

        return result

    def _score_items(self, items: List[Dict], optimize_for: str) -> List[Dict]:
        """Each item এর objective score calculate করো।"""
        scored = []
        for item in items:
            ctr     = float(item.get('ctr', 0.08))
            cvr     = float(item.get('cvr', 0.15))
            reward  = float(item.get('reward', 100))
            quality = float(item.get('quality_score', 0.7))

            if optimize_for == 'ctr':
                obj_score = ctr
            elif optimize_for == 'revenue':
                obj_score = ctr * cvr * reward
            elif optimize_for == 'conversion':
                obj_score = ctr * cvr
            else:  # engagement
                obj_score = ctr * quality
            scored.append({**item, 'objective_score': round(obj_score, 6)})
        return scored

    def optimize_grid(self, items: List[Dict], rows: int = 3, cols: int = 3) -> List[List[Dict]]:
        """Grid layout এ items optimally arrange করো (mobile UI)।"""
        optimized_flat = self.optimize(items, rows * cols, 'revenue')
        grid = []
        for r in range(rows):
            row = optimized_flat[r * cols: (r + 1) * cols]
            grid.append(row)
        return grid

    def ab_test_placement(self, variant_a: List[Dict], variant_b: List[Dict]) -> dict:
        """Two placement strategies compare করো।"""
        rev_a = sum(i.get('expected_revenue', 0) for i in variant_a)
        rev_b = sum(i.get('expected_revenue', 0) for i in variant_b)
        return {
            'variant_a_revenue': round(rev_a, 2),
            'variant_b_revenue': round(rev_b, 2),
            'winner':            'A' if rev_a >= rev_b else 'B',
            'lift_pct':          round(abs(rev_a - rev_b) / max(min(rev_a, rev_b), 0.001) * 100, 2),
        }

    def optimal_timing_by_position(self, position: int) -> dict:
        """কোন position এ কোন সময় best performance দেয়।"""
        timing_data = {
            1: {'peak_hours': [8, 9, 19, 20], 'note': 'Top position — all day good'},
            2: {'peak_hours': [10, 11, 18, 21], 'note': 'Second position — morning/evening'},
            3: {'peak_hours': [12, 13, 17, 22], 'note': 'Third — lunch/late evening'},
        }
        default = {'peak_hours': [10, 20], 'note': 'Standard engagement hours'}
        return timing_data.get(position, default)
