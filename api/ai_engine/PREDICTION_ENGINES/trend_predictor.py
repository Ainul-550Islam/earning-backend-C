"""
api/ai_engine/PREDICTION_ENGINES/trend_predictor.py
====================================================
Trend Predictor — emerging trends detection ও prediction।
Platform trends, user behavior trends, offer performance trends।
Marketing decisions ও inventory planning এ ব্যবহার।
"""

import logging
import math
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class TrendPredictor:
    """
    Multi-signal trend prediction engine।
    Time series analysis + seasonality + growth models।
    """

    def predict_trend(self, time_series: List[float], window: int = 7,
                      horizon: int = 7) -> dict:
        """Trend detect ও future predict করো।"""
        if len(time_series) < window:
            return {'trend': 'insufficient_data', 'forecast': [], 'confidence': 0.0}

        recent  = time_series[-window:]
        earlier = time_series[-window * 2: -window] if len(time_series) >= window * 2 else time_series[:window]

        avg_r = sum(recent) / len(recent)
        avg_e = sum(earlier) / len(earlier) if earlier else avg_r

        pct_change = ((avg_r - avg_e) / max(abs(avg_e), 0.001)) * 100

        if pct_change > 25:   trend, strength, conf = 'explosive_growth',    'very_strong', 0.88
        elif pct_change > 10: trend, strength, conf = 'strong_uptrend',      'strong',      0.82
        elif pct_change > 3:  trend, strength, conf = 'uptrend',             'moderate',    0.75
        elif pct_change > -3: trend, strength, conf = 'sideways',            'weak',        0.70
        elif pct_change > -10: trend, strength, conf = 'downtrend',          'moderate',    0.75
        elif pct_change > -25: trend, strength, conf = 'strong_downtrend',   'strong',      0.82
        else:                  trend, strength, conf = 'sharp_decline',      'very_strong', 0.88

        # Forecast next horizon days
        slope    = (avg_r - avg_e) / max(window, 1)
        forecast = [round(max(0, avg_r + slope * (i + 1)), 4) for i in range(horizon)]

        # Acceleration (second derivative)
        accel = slope - (avg_e - (sum(time_series[:window]) / max(window, 1))) / max(window, 1)

        return {
            'trend':         trend,
            'strength':      strength,
            'pct_change':    round(pct_change, 2),
            'avg_recent':    round(avg_r, 4),
            'avg_earlier':   round(avg_e, 4),
            'slope':         round(slope, 6),
            'acceleration':  round(accel, 6),
            'forecast':      forecast,
            'confidence':    conf,
            'is_positive':   pct_change > 0,
        }

    def detect_breakout(self, series: List[float], threshold: float = 2.0) -> dict:
        """Statistical breakout detection (price/metric spike)।"""
        if len(series) < 5:
            return {'breakout': False}

        baseline = series[:-1]
        current  = series[-1]
        mean = sum(baseline) / len(baseline)
        std  = math.sqrt(sum((x - mean) ** 2 for x in baseline) / max(len(baseline) - 1, 1)) or 0.001
        z    = (current - mean) / std

        return {
            'breakout':       abs(z) >= threshold,
            'direction':      'up' if z > 0 else 'down',
            'z_score':        round(z, 4),
            'current':        current,
            'baseline_mean':  round(mean, 4),
            'baseline_std':   round(std, 4),
            'severity':       'extreme' if abs(z) >= 4 else 'high' if abs(z) >= 3 else 'moderate',
        }

    def predict_platform_trends(self, tenant_id=None) -> dict:
        """Platform-level trend summary।"""
        from django.utils import timezone
        from datetime import timedelta

        trends = {}
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            days_7  = timezone.now() - timedelta(days=7)
            days_14 = timezone.now() - timedelta(days=14)
            users_7  = User.objects.filter(date_joined__gte=days_7).count()
            users_14 = User.objects.filter(date_joined__gte=days_14, date_joined__lt=days_7).count()
            trends['user_acquisition'] = {
                'current_week': users_7,
                'prev_week':    users_14,
                'trend':        'growing' if users_7 > users_14 else 'declining',
                'pct_change':   round((users_7 - users_14) / max(users_14, 1) * 100, 2),
            }
        except Exception:
            pass

        return {'platform_trends': trends, 'generated_at': str(timezone.now())}

    def emerging_offer_trends(self, lookback_days: int = 7) -> List[Dict]:
        """কোন offer categories trending হচ্ছে সেটা detect করো।"""
        try:
            from ..models import RecommendationResult
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count

            since = timezone.now() - timedelta(days=lookback_days)
            top = (RecommendationResult.objects
                   .filter(created_at__gte=since)
                   .values('item_type')
                   .annotate(count=Count('id'))
                   .order_by('-count')[:5])
            return [{'item_type': r['item_type'], 'request_count': r['count']} for r in top]
        except Exception as e:
            logger.error(f"Offer trend error: {e}")
            return []
