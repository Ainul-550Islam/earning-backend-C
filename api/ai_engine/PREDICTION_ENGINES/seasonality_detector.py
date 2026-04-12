"""
api/ai_engine/PREDICTION_ENGINES/seasonality_detector.py
=========================================================
Seasonality Detector — periodic patterns in time-series।
Weekly, monthly, yearly seasonality।
"""
import logging, math
from typing import List, Dict
logger = logging.getLogger(__name__)

class SeasonalityDetector:
    """Time-series seasonality detection engine।"""

    def detect_weekly_pattern(self, daily_data: Dict[str, float]) -> dict:
        if not daily_data:
            return {"has_seasonality": False}
        values = list(daily_data.values())
        avg    = sum(values) / len(values)
        patterns = {}
        for day, val in daily_data.items():
            relative = round(val / max(avg, 0.001), 3)
            patterns[day] = {
                "value":    val,
                "relative": relative,
                "type":     "peak" if relative > 1.15 else "trough" if relative < 0.85 else "normal",
            }
        peak_days   = [d for d, v in patterns.items() if v["type"] == "peak"]
        trough_days = [d for d, v in patterns.items() if v["type"] == "trough"]
        return {
            "has_seasonality": len(peak_days) > 0 or len(trough_days) > 0,
            "peak_days":       peak_days,
            "trough_days":     trough_days,
            "patterns":        patterns,
            "overall_avg":     round(avg, 4),
            "recommendation":  f"Best days: {', '.join(peak_days)}" if peak_days else "No clear pattern",
        }

    def detect_monthly_pattern(self, monthly_data: Dict[str, float]) -> dict:
        if not monthly_data: return {"has_seasonality": False}
        values = list(monthly_data.values())
        avg = sum(values) / len(values)
        peaks = {m: round(v/max(avg,0.001), 3) for m, v in monthly_data.items() if v/max(avg,0.001) > 1.10}
        return {
            "has_seasonality": bool(peaks),
            "peak_months":     list(peaks.keys()),
            "peak_multipliers": peaks,
            "avg_baseline":    round(avg, 4),
        }

    def decompose(self, series: List[float], period: int = 7) -> dict:
        """Simple STL-like decomposition।"""
        n = len(series)
        if n < period * 2:
            return {"trend": series, "seasonal": [0]*n, "residual": [0]*n}
        # Trend: moving average
        half = period // 2
        trend = []
        for i in range(n):
            start = max(0, i - half)
            end   = min(n, i + half + 1)
            trend.append(sum(series[start:end]) / (end - start))
        # Seasonal: average by position in period
        seasonal_avgs = [0.0] * period
        for i in range(n):
            seasonal_avgs[i % period] += series[i] - trend[i]
        counts = [n // period + (1 if i < n % period else 0) for i in range(period)]
        seasonal_avgs = [s/max(c,1) for s,c in zip(seasonal_avgs, counts)]
        seasonal = [seasonal_avgs[i % period] for i in range(n)]
        residual = [series[i] - trend[i] - seasonal[i] for i in range(n)]
        return {
            "trend":    [round(t, 4) for t in trend],
            "seasonal": [round(s, 4) for s in seasonal],
            "residual": [round(r, 4) for r in residual],
            "period":   period,
        }
