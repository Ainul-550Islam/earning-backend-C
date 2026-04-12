"""
api/ai_engine/PREDICTION_ENGINES/demand_forecast.py
====================================================
Demand Forecaster — offer/product demand prediction।
Time-series forecasting, seasonality adjustment।
Ad budget planning ও inventory management।
"""
import logging, math
from typing import List, Dict
logger = logging.getLogger(__name__)

class DemandForecaster:
    def forecast(self, historical: List[float], days: int = 7,
                 method: str = 'linear') -> dict:
        if not historical or len(historical) < 3:
            return {'forecast': [0.0]*days, 'method': 'no_data', 'confidence': 0.0}
        if method == 'linear':   return self._linear(historical, days)
        if method == 'exp':      return self._exp_smooth(historical, days)
        if method == 'seasonal': return self._seasonal(historical, days)
        return self._linear(historical, days)

    def _linear(self, data: List[float], days: int) -> dict:
        n     = len(data)
        avg   = sum(data) / n
        trend = (data[-1] - data[0]) / max(n-1, 1)
        forecast = [round(max(0, avg + trend*(i+1)), 2) for i in range(days)]
        r2    = self._r_squared(data, [avg + trend*i for i in range(n)])
        return {
            'forecast':   forecast,
            'total':      round(sum(forecast), 2),
            'trend':      'growing' if trend > 0 else 'declining' if trend < 0 else 'stable',
            'confidence': round(max(0.3, r2), 4),
            'method':     'linear',
        }

    def _exp_smooth(self, data: List[float], days: int, alpha: float = 0.3) -> dict:
        s = data[0]
        for v in data[1:]:
            s = alpha*v + (1-alpha)*s
        forecast = [round(max(0, s), 2)] * days
        return {'forecast': forecast, 'method': 'exp_smoothing', 'confidence': 0.60}

    def _seasonal(self, data: List[float], days: int, period: int = 7) -> dict:
        if len(data) < period*2:
            return self._linear(data, days)
        seasonal_idx = [sum(data[i::period])/max(len(data[i::period]),1) for i in range(period)]
        avg = sum(data[-period:]) / period
        forecast = [round(max(0, avg * (seasonal_idx[i%period]/max(sum(seasonal_idx)/period,0.001))), 2) for i in range(days)]
        return {'forecast': forecast, 'method': 'seasonal', 'confidence': 0.65}

    def _r_squared(self, actual: List[float], predicted: List[float]) -> float:
        if not actual: return 0.0
        ymean = sum(actual)/len(actual)
        ss_tot = sum((y-ymean)**2 for y in actual)
        ss_res = sum((y-p)**2 for y,p in zip(actual,predicted))
        return max(0.0, 1 - ss_res/max(ss_tot,0.001))

    def forecast_offer_demand(self, offer_id: str, historical_clicks: List[float],
                               days: int = 7) -> dict:
        result = self.forecast(historical_clicks, days)
        total_demand = sum(result.get('forecast', []))
        return {
            **result,
            'offer_id':      offer_id,
            'total_demand':  round(total_demand, 0),
            'peak_day':      result.get('forecast', [0]*days).index(max(result.get('forecast', [0]*days))) + 1 if result.get('forecast') else 1,
        }

    def detect_demand_spike(self, recent: List[float], baseline: List[float]) -> dict:
        if not recent or not baseline: return {'spike': False}
        avg_recent   = sum(recent)/len(recent)
        avg_baseline = sum(baseline)/len(baseline)
        ratio = avg_recent / max(avg_baseline, 0.001)
        return {
            'spike':       ratio >= 2.0,
            'ratio':       round(ratio, 4),
            'pct_increase': round((ratio-1)*100, 2),
            'severity':    'extreme' if ratio >= 5 else 'high' if ratio >= 3 else 'moderate' if ratio >= 2 else 'normal',
        }

    def seasonal_decompose(self, data: List[float], period: int = 7) -> dict:
        if len(data) < period*2: return {'seasonal': [], 'trend': [], 'residual': []}
        n = len(data)
        trend = [sum(data[max(0,i-period//2):i+period//2+1])/period for i in range(n)]
        seasonal = [data[i] - trend[i] for i in range(n)]
        avg_seasonal = [sum(seasonal[i::period])/max(len(seasonal[i::period]),1) for i in range(period)]
        residual = [data[i] - trend[i] - avg_seasonal[i%period] for i in range(n)]
        return {
            'trend':    [round(v,4) for v in trend],
            'seasonal': [round(v,4) for v in avg_seasonal],
            'residual': [round(v,4) for v in residual],
            'period':   period,
        }
