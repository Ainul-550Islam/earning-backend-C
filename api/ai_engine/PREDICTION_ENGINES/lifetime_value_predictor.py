"""
api/ai_engine/PREDICTION_ENGINES/lifetime_value_predictor.py
=============================================================
Lifetime Value (LTV) Predictor — customer lifetime value calculation।
RFM model + behavioral signals + referral network value।
Marketing budget allocation ও user tier decisions।
"""
import logging
from typing import Dict, List
from ..utils import days_since, safe_ratio, get_ltv_segment
logger = logging.getLogger(__name__)

class LifetimeValuePredictor:
    """RFM-based LTV prediction with referral bonus।"""

    def predict(self, user, extra: dict = None) -> dict:
        extra        = extra or {}
        age          = max(1, days_since(user.date_joined))
        total_earned = float(getattr(user, 'total_earned', 0))
        coin_balance = float(getattr(user, 'coin_balance', 0))
        days_inactive = days_since(user.last_login)
        offers_done   = extra.get('offers_completed', 0)
        referrals     = extra.get('referral_count', 0)
        streak        = extra.get('streak_days', 0)
        avg_daily     = safe_ratio(total_earned, age)

        # RFM scores (0-1)
        recency  = max(0.0, 1.0 - days_inactive / 30)
        frequency = min(1.0, offers_done / 50)
        monetary  = min(1.0, total_earned / 10000)
        rfm       = recency*0.30 + frequency*0.30 + monetary*0.40

        # Multipliers
        mult = 1.0
        if streak >= 30:  mult *= 1.20
        elif streak >= 7: mult *= 1.10
        if referrals >= 10: mult *= 1.25
        elif referrals >= 5: mult *= 1.15
        if coin_balance >= 5000: mult *= 1.10

        # LTV = annualized earning * RFM * multiplier
        ltv_base       = avg_daily * 365 * rfm * mult
        referral_bonus = referrals * 75  # BDT per referral network value
        ltv            = round(ltv_base + referral_bonus, 2)

        # Percentile vs platform average (assumed avg_ltv = 2000)
        percentile = min(99, int(ltv / 2000 * 50))

        return {
            'user_id':          str(user.id),
            'ltv':              ltv,
            'ltv_segment':      get_ltv_segment(ltv),
            'rfm_score':        round(rfm, 4),
            'recency':          round(recency, 4),
            'frequency':        round(frequency, 4),
            'monetary':         round(monetary, 4),
            'growth_multiplier': round(mult, 4),
            'avg_daily_earn':   round(avg_daily, 4),
            'referral_value':   round(referral_bonus, 2),
            'percentile':       percentile,
            'confidence':       0.72,
            'action':           self._ltv_action(ltv, rfm),
        }

    def _ltv_action(self, ltv: float, rfm: float) -> str:
        if ltv >= 10000:  return 'VIP treatment — personal account manager'
        if ltv >= 5000:   return 'Premium offers — increase earning limits'
        if ltv >= 2000:   return 'Loyalty rewards — bonus streak multiplier'
        if rfm < 0.30:    return 'Re-engagement campaign — prevent churn'
        return 'Standard engagement — monitor growth'

    def predict_cohort_ltv(self, users: List) -> dict:
        results   = [self.predict(u) for u in users]
        ltvs      = [r['ltv'] for r in results]
        total_ltv = sum(ltvs)
        segs      = {}
        for r in results:
            seg = r['ltv_segment']
            segs[seg] = segs.get(seg, 0) + 1
        return {
            'total_users':   len(users),
            'total_ltv':     round(total_ltv, 2),
            'avg_ltv':       round(total_ltv/max(len(users),1), 2),
            'max_ltv':       round(max(ltvs), 2) if ltvs else 0,
            'min_ltv':       round(min(ltvs), 2) if ltvs else 0,
            'segments':      segs,
            'premium_users': segs.get('premium', 0),
        }

    def calculate_cac_ltv_ratio(self, ltv: float, cac: float) -> dict:
        if cac <= 0: return {'ratio': 0, 'verdict': 'no_cac_data'}
        ratio = ltv / cac
        return {
            'ltv': ltv, 'cac': cac,
            'ltv_cac_ratio': round(ratio, 2),
            'verdict': 'excellent' if ratio >= 5 else 'good' if ratio >= 3 else 'acceptable' if ratio >= 1 else 'poor',
            'recommendation': 'Scale acquisition' if ratio >= 3 else 'Reduce CAC or increase LTV',
        }
