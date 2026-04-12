"""
api/ai_engine/ANALYTICS_INSIGHTS/segmentation_analyzer.py
==========================================================
Segmentation Analyzer — user segment performance analysis।
RFM analysis, cohort comparison, segment profitability।
Business intelligence ও marketing strategy এর জন্য।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SegmentationAnalyzer:
    """
    User segment performance analyzer।
    Compare, rank, profile segments।
    """

    def compare_segments(self, segments: Dict[str, List[float]],
                          metric_name: str = 'revenue') -> dict:
        """Segment performance compare করো।"""
        if not segments:
            return {'error': 'No segment data'}

        stats = {}
        for seg, values in segments.items():
            if not values:
                continue
            n    = len(values)
            mean = sum(values) / n
            variance = sum((x - mean) ** 2 for x in values) / max(n - 1, 1)
            std = variance ** 0.5

            stats[seg] = {
                'count':  n,
                'mean':   round(mean, 4),
                'std':    round(std, 4),
                'min':    round(min(values), 4),
                'max':    round(max(values), 4),
                'median': round(sorted(values)[n // 2], 4),
                'total':  round(sum(values), 4),
            }

        if stats:
            best  = max(stats, key=lambda s: stats[s]['mean'])
            worst = min(stats, key=lambda s: stats[s]['mean'])
        else:
            best = worst = None

        return {
            'metric':        metric_name,
            'segments':      stats,
            'best_segment':  best,
            'worst_segment': worst,
            'segment_count': len(stats),
        }

    def rfm_analysis(self, users: List[Dict]) -> Dict[str, List[str]]:
        """
        RFM (Recency, Frequency, Monetary) segmentation।
        Each user classify করো।
        """
        segments: Dict[str, List[str]] = {
            'champions':        [],
            'loyal':            [],
            'potential_loyalist': [],
            'at_risk':          [],
            'cant_lose':        [],
            'hibernating':      [],
            'lost':             [],
        }

        for u in users:
            recency   = u.get('days_since_last_activity', 999)
            frequency = u.get('transaction_count', 0)
            monetary  = u.get('total_spent', 0)
            uid       = str(u.get('user_id', ''))

            if recency <= 7 and frequency >= 10 and monetary >= 1000:
                segments['champions'].append(uid)
            elif recency <= 14 and frequency >= 5:
                segments['loyal'].append(uid)
            elif recency <= 30 and frequency >= 2:
                segments['potential_loyalist'].append(uid)
            elif recency > 30 and frequency >= 5:
                segments['at_risk'].append(uid)
            elif recency > 60 and monetary >= 500:
                segments['cant_lose'].append(uid)
            elif recency > 60 and frequency >= 1:
                segments['hibernating'].append(uid)
            else:
                segments['lost'].append(uid)

        return {k: v for k, v in segments.items() if v}

    def segment_profitability(self, segment_data: List[Dict]) -> List[Dict]:
        """Each segment এর profitability rank করো।"""
        enriched = []
        for seg in segment_data:
            revenue = seg.get('total_revenue', 0)
            cost    = seg.get('total_cost', 0)
            users   = max(seg.get('user_count', 1), 1)
            profit  = revenue - cost
            arpu    = revenue / users

            enriched.append({
                **seg,
                'profit':       round(profit, 2),
                'profit_margin': round(profit / max(revenue, 0.001) * 100, 2),
                'arpu':         round(arpu, 2),
                'tier':         'premium' if arpu >= 500 else 'standard' if arpu >= 100 else 'basic',
            })

        return sorted(enriched, key=lambda x: x.get('arpu', 0), reverse=True)

    def lifetime_segment_analysis(self, cohorts: Dict[str, Dict]) -> dict:
        """Cohort lifetime value analysis।"""
        results = {}
        for cohort_name, data in cohorts.items():
            retention  = data.get('retention_rate', 0)
            arpu       = data.get('arpu', 0)
            churn_rate = data.get('churn_rate', 0.05)
            ltv        = round(arpu / max(churn_rate, 0.001), 2) if churn_rate > 0 else arpu * 12

            results[cohort_name] = {
                'retention':   retention,
                'arpu':        arpu,
                'ltv':         ltv,
                'ltv_tier':    'high' if ltv >= 2000 else 'medium' if ltv >= 500 else 'low',
            }

        return {
            'cohorts':    results,
            'best_cohort': max(results, key=lambda k: results[k]['ltv']) if results else None,
        }
