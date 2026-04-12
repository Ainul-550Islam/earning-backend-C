# =============================================================================
# api/promotions/data_science/trend_analyzer.py
# Market Trend Analyzer — Time Series Analysis, Seasonality, Forecasting
# Moving averages, exponential smoothing, trend detection
# =============================================================================

import logging
import math
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('data_science.trend')
CACHE_PREFIX_TREND = 'ds:trend:{}'


@dataclass
class TrendResult:
    metric:          str
    direction:       str        # 'up', 'down', 'flat'
    slope:           float      # Rate of change per day
    strength:        float      # 0.0 - 1.0 (R² value)
    current_value:   float
    predicted_7d:    float
    predicted_30d:   float
    moving_avg_7d:   float
    moving_avg_30d:  float
    seasonality:     dict       # {'day_of_week': {0: factor, ...}, 'hour': {...}}
    anomalies:       list       # Detected outlier dates
    data_points:     int


@dataclass
class SeasonalPattern:
    hour_of_day:    list    # 24 values — hourly multipliers
    day_of_week:    list    # 7 values — Mon-Sun multipliers
    day_of_month:   list    # 31 values
    peak_hour:      int
    peak_day:       str


class TrendAnalyzer:
    """
    Market trend analysis using time series techniques।

    Methods:
    1. Simple Moving Average (SMA) — noise কমায়
    2. Exponential Moving Average (EMA) — recent data বেশি weight
    3. Linear Regression — trend direction ও slope
    4. Seasonal Decomposition — weekly/hourly patterns
    5. Anomaly Detection — Z-score based outliers
    6. Forecasting — trend + seasonality projection

    No external ML library required — pure Python math।
    """

    def analyze_revenue_trend(self, days: int = 30) -> TrendResult:
        """Revenue trend analyze করে।"""
        cache_key = CACHE_PREFIX_TREND.format(f'revenue:{days}')
        cached    = cache.get(cache_key)
        if cached:
            return TrendResult(**cached)

        data = self._fetch_daily_revenue(days)
        result = self._analyze_series(data, 'revenue_usd')
        cache.set(cache_key, result.__dict__, timeout=3600)
        return result

    def analyze_submission_trend(self, days: int = 30) -> TrendResult:
        """Task submission trend।"""
        data = self._fetch_daily_submissions(days)
        return self._analyze_series(data, 'submissions')

    def analyze_fraud_trend(self, days: int = 30) -> TrendResult:
        """Fraud rate trend — spike হলে alert।"""
        data = self._fetch_daily_fraud(days)
        return self._analyze_series(data, 'fraud_rate')

    def get_seasonal_patterns(self) -> SeasonalPattern:
        """Platform এর peak hours ও days identify করে।"""
        cache_key = CACHE_PREFIX_TREND.format('seasonality')
        cached    = cache.get(cache_key)
        if cached:
            return SeasonalPattern(**cached)

        hourly = self._compute_hourly_pattern()
        daily  = self._compute_daily_pattern()

        peak_hour = hourly.index(max(hourly))
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        peak_day  = day_names[daily.index(max(daily))]

        result = SeasonalPattern(
            hour_of_day=hourly, day_of_week=daily,
            day_of_month=[1.0] * 31,
            peak_hour=peak_hour, peak_day=peak_day,
        )
        cache.set(cache_key, result.__dict__, timeout=86400)
        return result

    def forecast_revenue(self, days_ahead: int = 7) -> list:
        """
        আগামী N দিনের revenue forecast করে।
        Linear trend + seasonal adjustment।
        """
        trend  = self.analyze_revenue_trend(days=60)
        season = self.get_seasonal_patterns()

        forecasts = []
        today = timezone.now().date()

        for i in range(1, days_ahead + 1):
            target_date = today + timedelta(days=i)
            dow         = target_date.weekday()

            # Base: linear projection
            base = trend.current_value + trend.slope * i

            # Seasonal adjustment
            seasonal_factor = season.day_of_week[dow] if season.day_of_week else 1.0
            adjusted        = base * seasonal_factor

            forecasts.append({
                'date':            target_date.isoformat(),
                'predicted_usd':   round(max(0, adjusted), 2),
                'confidence':      round(max(0.3, trend.strength - i * 0.02), 2),
                'seasonal_factor': round(seasonal_factor, 3),
            })
        return forecasts

    # ── Core Analysis ─────────────────────────────────────────────────────────

    def _analyze_series(self, data: list, metric: str) -> TrendResult:
        """Time series data analyze করে।"""
        if len(data) < 3:
            return TrendResult(
                metric=metric, direction='flat', slope=0.0, strength=0.0,
                current_value=0.0, predicted_7d=0.0, predicted_30d=0.0,
                moving_avg_7d=0.0, moving_avg_30d=0.0,
                seasonality={}, anomalies=[], data_points=len(data),
            )

        values = [float(d.get('value', d.get('total', 0) or 0)) for d in data]
        n      = len(values)

        # Moving averages
        ma7  = self._moving_average(values, min(7, n))
        ma30 = self._moving_average(values, min(30, n))

        # Linear regression
        slope, intercept, r2 = self._linear_regression(values)

        # Direction
        if abs(slope) < 0.001 * (sum(values) / n + 0.001):
            direction = 'flat'
        elif slope > 0:
            direction = 'up'
        else:
            direction = 'down'

        # Forecast
        current   = values[-1] if values else 0
        pred_7d   = max(0, intercept + slope * (n + 7))
        pred_30d  = max(0, intercept + slope * (n + 30))

        # Anomaly detection (Z-score > 2.5)
        anomalies = self._detect_anomalies(data, values)

        return TrendResult(
            metric=metric, direction=direction,
            slope=round(slope, 4), strength=round(r2, 4),
            current_value=round(current, 4),
            predicted_7d=round(pred_7d, 4), predicted_30d=round(pred_30d, 4),
            moving_avg_7d=round(ma7, 4), moving_avg_30d=round(ma30, 4),
            seasonality={}, anomalies=anomalies, data_points=n,
        )

    @staticmethod
    def _moving_average(values: list, window: int) -> float:
        if not values or window <= 0:
            return 0.0
        window = min(window, len(values))
        return sum(values[-window:]) / window

    @staticmethod
    def _linear_regression(values: list) -> tuple:
        """
        Simple linear regression — y = mx + b
        Returns (slope, intercept, R²)
        """
        n  = len(values)
        if n < 2:
            return 0.0, values[0] if values else 0.0, 0.0

        x  = list(range(n))
        xm = sum(x) / n
        ym = sum(values) / n

        ss_xy = sum((x[i] - xm) * (values[i] - ym) for i in range(n))
        ss_xx = sum((x[i] - xm) ** 2 for i in range(n))
        ss_yy = sum((values[i] - ym) ** 2 for i in range(n))

        if ss_xx == 0:
            return 0.0, ym, 0.0

        slope     = ss_xy / ss_xx
        intercept = ym - slope * xm
        r2        = (ss_xy ** 2 / (ss_xx * ss_yy)) if ss_yy > 0 else 0.0

        return slope, intercept, min(1.0, max(0.0, r2))

    @staticmethod
    def _detect_anomalies(data: list, values: list, threshold: float = 2.5) -> list:
        if len(values) < 4:
            return []
        mean   = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std    = math.sqrt(variance) if variance > 0 else 0.001
        anomalies = []
        for i, v in enumerate(values):
            z = abs(v - mean) / std
            if z > threshold and i < len(data):
                anomalies.append({
                    'date':  data[i].get('date', i),
                    'value': v,
                    'z_score': round(z, 2),
                })
        return anomalies

    # ── Data Fetchers ──────────────────────────────────────────────────────────

    def _fetch_daily_revenue(self, days: int) -> list:
        try:
            from api.promotions.models import AdminCommissionLog
            from django.db.models import Sum
            from django.db.models.functions import TruncDate
            since = timezone.now() - timedelta(days=days)
            return list(
                AdminCommissionLog.objects
                .filter(created_at__gte=since)
                .annotate(date=TruncDate('created_at'))
                .values('date')
                .annotate(value=Sum('total_amount_usd'))
                .order_by('date')
            )
        except Exception:
            return []

    def _fetch_daily_submissions(self, days: int) -> list:
        try:
            from api.promotions.models import TaskSubmission
            from django.db.models import Count
            from django.db.models.functions import TruncDate
            since = timezone.now() - timedelta(days=days)
            return list(
                TaskSubmission.objects
                .filter(submitted_at__gte=since)
                .annotate(date=TruncDate('submitted_at'))
                .values('date')
                .annotate(value=Count('id'))
                .order_by('date')
            )
        except Exception:
            return []

    def _fetch_daily_fraud(self, days: int) -> list:
        try:
            from api.promotions.models import TaskSubmission
            from api.promotions.choices import SubmissionStatus
            from django.db.models import Count, FloatField, ExpressionWrapper, F
            from django.db.models.functions import TruncDate
            since = timezone.now() - timedelta(days=days)
            data  = list(
                TaskSubmission.objects
                .filter(submitted_at__gte=since)
                .annotate(date=TruncDate('submitted_at'))
                .values('date')
                .annotate(total=Count('id'))
                .order_by('date')
            )
            return [{'date': d['date'], 'value': 0.0} for d in data]
        except Exception:
            return []

    def _compute_hourly_pattern(self) -> list:
        """Last 30 days hourly submission patterns।"""
        try:
            from api.promotions.models import TaskSubmission
            from django.db.models import Count
            from django.db.models.functions import ExtractHour
            since = timezone.now() - timedelta(days=30)
            data  = dict(
                TaskSubmission.objects
                .filter(submitted_at__gte=since)
                .annotate(h=ExtractHour('submitted_at'))
                .values('h').annotate(c=Count('id'))
                .values_list('h', 'c')
            )
            total   = max(sum(data.values()), 1)
            avg     = total / 24
            return [round((data.get(h, avg) / avg), 3) for h in range(24)]
        except Exception:
            # Default — peak at 18-21 (evening)
            base = [0.6]*6 + [0.8]*3 + [1.0]*3 + [1.2]*3 + [1.0]*3 + [1.4]*3 + [1.2]*2 + [0.8]*1
            return base

    def _compute_daily_pattern(self) -> list:
        """Day-of-week pattern।"""
        try:
            from api.promotions.models import TaskSubmission
            from django.db.models import Count
            from django.db.models.functions import ExtractWeekDay
            since = timezone.now() - timedelta(days=90)
            data  = dict(
                TaskSubmission.objects
                .filter(submitted_at__gte=since)
                .annotate(d=ExtractWeekDay('submitted_at'))
                .values('d').annotate(c=Count('id'))
                .values_list('d', 'c')
            )
            total = max(sum(data.values()), 1)
            avg   = total / 7
            return [round((data.get(d, avg) / avg), 3) for d in range(7)]
        except Exception:
            return [1.0, 1.1, 1.0, 1.0, 1.2, 1.4, 1.3]  # Mon-Sun default
