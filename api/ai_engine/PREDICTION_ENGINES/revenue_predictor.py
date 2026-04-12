"""
api/ai_engine/PREDICTION_ENGINES/revenue_predictor.py
======================================================
Revenue Predictor — user ও platform revenue forecasting।
Historical earning data + growth modeling।
Marketing budget allocation ও ROI forecasting।
"""
import logging, math
from typing import List, Dict
from ..utils import days_since, safe_ratio
logger = logging.getLogger(__name__)

class RevenuePredictor:
    def predict_user_revenue(self, user, days_ahead: int = 30,
                              extra_data: dict = None) -> dict:
        extra      = extra_data or {}
        age        = max(1, days_since(user.date_joined))
        total      = float(getattr(user, 'total_earned', 0))
        avg_daily  = safe_ratio(total, age)
        streak     = extra.get('streak_days', 0)
        referrals  = extra.get('referral_count', 0)
        activity   = extra.get('activity_score', 0.5)
        growth = 1.0
        if streak >= 30:  growth *= 1.15
        elif streak >= 7: growth *= 1.08
        if referrals >= 5:  growth *= 1.10
        if activity >= 0.8: growth *= 1.12
        elif activity < 0.3: growth *= 0.85
        predicted   = round(avg_daily * days_ahead * growth, 2)
        low_bound   = round(predicted * 0.70, 2)
        high_bound  = round(predicted * 1.40, 2)
        return {
            'user_id':          str(user.id),
            'days_ahead':       days_ahead,
            'predicted_revenue': predicted,
            'low_estimate':     low_bound,
            'high_estimate':    high_bound,
            'avg_daily_earn':   round(avg_daily, 4),
            'growth_factor':    round(growth, 4),
            'confidence':       0.65,
            'method':           'historical_growth_model',
        }

    def predict_platform_revenue(self, historical: List[float],
                                  days: int = 30) -> dict:
        if len(historical) < 7:
            return {'forecast': [], 'confidence': 0.3}
        n     = len(historical)
        avg   = sum(historical[-7:]) / 7
        trend = (historical[-1] - historical[-7]) / 7
        forecast = [round(max(0, avg + trend*(i+1)), 2) for i in range(days)]
        total    = sum(forecast)
        pct_change = (historical[-1]-historical[-7])/max(historical[-7], 0.001)*100
        return {
            'forecast':          forecast,
            'total_forecast':    round(total, 2),
            'avg_daily':         round(total/days, 2),
            'trend':             'growing' if trend > 0 else 'declining',
            'pct_change_7d':     round(pct_change, 2),
            'confidence':        0.70,
        }

    def predict_campaign_roi(self, spend: float, predicted_conversions: int,
                              avg_revenue_per_conv: float) -> dict:
        revenue  = predicted_conversions * avg_revenue_per_conv
        roi      = (revenue - spend) / max(spend, 0.001)
        roas     = revenue / max(spend, 0.001)
        cpa      = spend / max(predicted_conversions, 1)
        return {
            'spend':           spend,
            'predicted_revenue': round(revenue, 2),
            'roi':             round(roi, 4),
            'roas':            round(roas, 4),
            'cpa':             round(cpa, 2),
            'profitable':      roi > 0,
            'recommendation':  'Run campaign' if roi > 0.3 else 'Optimize first' if roi > 0 else 'Do not run',
        }

    def ltv_to_revenue_bridge(self, users: List[Dict]) -> dict:
        total_ltv = sum(float(u.get('ltv', 0)) for u in users)
        avg_ltv   = total_ltv / max(len(users), 1)
        segments  = {'premium':0,'high':0,'medium':0,'low':0}
        for u in users:
            ltv = float(u.get('ltv', 0))
            if ltv >= 10000: segments['premium'] += 1
            elif ltv >= 2000: segments['high'] += 1
            elif ltv >= 500: segments['medium'] += 1
            else: segments['low'] += 1
        return {
            'user_count':   len(users),
            'total_ltv':    round(total_ltv, 2),
            'avg_ltv':      round(avg_ltv, 2),
            'ltv_segments': segments,
            'revenue_potential_12m': round(total_ltv * 0.25, 2),
        }
