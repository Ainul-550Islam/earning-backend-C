"""
api/ai_engine/ANALYTICS_INSIGHTS/predictive_analytics.py
=========================================================
Predictive Analytics — forward-looking business insights।
Revenue forecast, user growth, offer performance predictions।
"""

import logging
import math
from typing import List, Dict

logger = logging.getLogger(__name__)


class PredictiveAnalytics:
    """Forward-looking predictive analytics engine।"""

    def predict_metric(self, historical: List[float], periods: int = 7,
                        method: str = 'linear') -> dict:
        if not historical or len(historical) < 2:
            return {'forecast': [], 'method': method, 'confidence': 0.0}

        if method == 'linear':
            return self._linear_forecast(historical, periods)
        elif method == 'exponential':
            return self._exp_smoothing(historical, periods)
        elif method == 'moving_average':
            return self._moving_average_forecast(historical, periods)
        return self._linear_forecast(historical, periods)

    def _linear_forecast(self, data: List[float], periods: int) -> dict:
        n     = len(data)
        xs    = list(range(n))
        x_bar = sum(xs) / n
        y_bar = sum(data) / n
        slope = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, data)) / max(sum((x - x_bar)**2 for x in xs), 0.001)
        intercept = y_bar - slope * x_bar

        forecast = [round(max(0, intercept + slope * (n + i)), 4) for i in range(periods)]
        r_squared = self._r_squared(data, [intercept + slope * x for x in xs])

        return {
            'forecast':   forecast,
            'method':     'linear_regression',
            'slope':      round(slope, 6),
            'r_squared':  round(r_squared, 4),
            'confidence': round(min(0.95, max(0.30, r_squared)), 4),
            'trend':      'growing' if slope > 0 else 'declining' if slope < 0 else 'stable',
        }

    def _exp_smoothing(self, data: List[float], periods: int, alpha: float = 0.3) -> dict:
        smoothed = [data[0]]
        for val in data[1:]:
            smoothed.append(alpha * val + (1 - alpha) * smoothed[-1])
        last = smoothed[-1]
        forecast = [round(max(0, last), 4)] * periods
        return {'forecast': forecast, 'method': 'exponential_smoothing', 'alpha': alpha, 'confidence': 0.65}

    def _moving_average_forecast(self, data: List[float], periods: int, window: int = 7) -> dict:
        w_data = data[-window:] if len(data) >= window else data
        avg    = sum(w_data) / len(w_data)
        return {'forecast': [round(avg, 4)] * periods, 'method': 'moving_average', 'window': window, 'confidence': 0.60}

    def _r_squared(self, actual: List[float], predicted: List[float]) -> float:
        if not actual:
            return 0.0
        y_bar   = sum(actual) / len(actual)
        ss_tot  = sum((y - y_bar) ** 2 for y in actual)
        ss_res  = sum((y - p) ** 2 for y, p in zip(actual, predicted))
        return max(0.0, 1 - ss_res / max(ss_tot, 0.001))

    def predict_revenue(self, historical_revenue: List[float], days: int = 30) -> dict:
        result = self.predict_metric(historical_revenue, days, 'linear')
        total_forecast = sum(result.get('forecast', []))
        return {
            **result,
            'total_forecast_revenue': round(total_forecast, 2),
            'avg_daily_forecast':     round(total_forecast / max(days, 1), 2),
        }

    def predict_user_growth(self, historical_users: List[int], days: int = 30) -> dict:
        data = [float(u) for u in historical_users]
        return self.predict_metric(data, days, 'exponential')

    def predict_churn_volume(self, tenant_id=None, days: int = 7) -> dict:
        try:
            from ..models import ChurnRiskProfile
            high_risk = ChurnRiskProfile.objects.filter(risk_level__in=['high','very_high']).count()
            estimated_churners = round(high_risk * 0.60)
            return {
                'at_risk_users':        high_risk,
                'estimated_churners':   estimated_churners,
                'forecast_days':        days,
                'intervention_needed':  high_risk > 100,
                'recommendation':       'Launch retention campaign immediately' if high_risk > 100 else 'Monitor',
            }
        except Exception:
            return {'estimated_churners': 0}
