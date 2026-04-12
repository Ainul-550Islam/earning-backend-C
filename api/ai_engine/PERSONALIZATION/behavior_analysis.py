"""
api/ai_engine/PERSONALIZATION/behavior_analysis.py
===================================================
Behavior Analysis — user session, click, earn behavior analysis।
Pattern detection, peak time analysis, device preference।
"""

import logging
from typing import List, Dict
from ..utils import safe_ratio

logger = logging.getLogger(__name__)


class BehaviorAnalyzer:
    """Comprehensive user behavioral pattern analyzer।"""

    def analyze_sessions(self, sessions: List[Dict]) -> dict:
        """Session history analyze করো।"""
        if not sessions:
            return {'pattern': 'no_data', 'sessions': 0}

        total   = len(sessions)
        durations = [s.get('duration_seconds', 0) for s in sessions]
        avg_dur   = sum(durations) / total

        hours = [s.get('hour', 12) for s in sessions]
        freq: Dict[int, int] = {}
        for h in hours:
            freq[h] = freq.get(h, 0) + 1
        peak_hour = max(freq, key=freq.get) if freq else 12

        devices: Dict[str, int] = {}
        for s in sessions:
            dev = s.get('device', 'mobile')
            devices[dev] = devices.get(dev, 0) + 1
        primary_device = max(devices, key=devices.get) if devices else 'mobile'

        conversions = sum(1 for s in sessions if s.get('converted'))
        cvr = safe_ratio(conversions, total)

        return {
            'total_sessions':      total,
            'avg_duration_min':    round(avg_dur / 60, 2),
            'peak_hour':           peak_hour,
            'is_morning_user':     6 <= peak_hour <= 11,
            'is_afternoon_user':   12 <= peak_hour <= 17,
            'is_evening_user':     18 <= peak_hour <= 23,
            'primary_device':      primary_device,
            'device_distribution': devices,
            'conversion_rate':     round(cvr, 4),
            'engagement_level':    self._engagement_level(total, avg_dur, cvr),
        }

    def _engagement_level(self, sessions: int, avg_dur: float, cvr: float) -> str:
        score = 0
        if sessions >= 20:  score += 2
        elif sessions >= 5: score += 1
        if avg_dur >= 300:  score += 2
        elif avg_dur >= 60: score += 1
        if cvr >= 0.20:     score += 2
        elif cvr >= 0.05:   score += 1
        if score >= 5: return 'highly_engaged'
        if score >= 3: return 'moderately_engaged'
        if score >= 1: return 'low_engagement'
        return 'dormant'

    def analyze_earning_pattern(self, transactions: List[Dict]) -> dict:
        """Earning transaction patterns analyze করো।"""
        if not transactions:
            return {'pattern': 'no_data'}

        amounts = [float(t.get('amount', 0)) for t in transactions]
        total_earned = sum(amounts)
        avg_amount   = total_earned / len(amounts) if amounts else 0

        days_with_earn: Dict[int, float] = {}
        for t in transactions:
            dow = t.get('day_of_week', 0)
            days_with_earn[dow] = days_with_earn.get(dow, 0) + float(t.get('amount', 0))

        best_day_num = max(days_with_earn, key=days_with_earn.get) if days_with_earn else 0
        day_names    = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        best_day     = day_names[best_day_num] if best_day_num < 7 else 'Mon'

        return {
            'total_earned':  round(total_earned, 2),
            'transaction_count': len(transactions),
            'avg_per_transaction': round(avg_amount, 2),
            'best_earning_day':   best_day,
            'consistency':        'consistent' if len(days_with_earn) >= 5 else 'sporadic',
            'earner_type':        self._earner_type(avg_amount, len(transactions)),
        }

    def _earner_type(self, avg: float, count: int) -> str:
        if avg >= 500 and count >= 10: return 'power_earner'
        if avg >= 100 and count >= 5:  return 'regular_earner'
        if count >= 20:                return 'frequent_small_earner'
        if count >= 1:                 return 'occasional_earner'
        return 'non_earner'

    def detect_behavior_change(self, recent: Dict, historical: Dict) -> dict:
        """Behavior পরিবর্তন detect করো।"""
        changes = []
        metrics = ['session_count', 'avg_duration', 'conversion_rate', 'total_earned']

        for metric in metrics:
            r_val = recent.get(metric, 0)
            h_val = historical.get(metric, 0)
            if h_val == 0:
                continue
            pct = (r_val - h_val) / h_val * 100
            if abs(pct) >= 20:
                changes.append({
                    'metric': metric,
                    'change_pct': round(pct, 2),
                    'direction': 'improved' if pct > 0 else 'declined',
                    'significant': abs(pct) >= 50,
                })

        return {
            'behavior_changed':  len(changes) > 0,
            'changes':           changes,
            'churn_signal':      any(c['metric'] in ['session_count','conversion_rate']
                                     and c['direction'] == 'declined' and c['significant']
                                     for c in changes),
        }
