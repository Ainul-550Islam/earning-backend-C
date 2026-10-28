"""
api/support/analytics/predictive_analytics.py
FILE 18/70 — Predictive Analytics

ML-based ticket volume forecasting।
Agent staffing recommendations।
Peak hour prediction।

Algorithms:
- Simple Moving Average (SMA)
- Weighted Moving Average (WMA)
- Seasonal decomposition
- Day-of-week patterns
"""
import logging
import math
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PredictiveAnalytics:
    """
    Ticket volume prediction engine।
    Historical data থেকে future volume predict করো।
    """

    CACHE_TTL = 3600  # 1 hour

    # ──────────────────────────────────────────
    # VOLUME FORECAST
    # ──────────────────────────────────────────
    def forecast_volume(self, days: int = 7) -> list:
        """
        আগামী N দিনের ticket volume forecast করো।
        Returns: [{date, predicted, lower, upper, day_name}]
        """
        cached = cache.get(f'forecast:{days}')
        if cached:
            return cached

        historical = self._get_historical_daily(days=90)  # 90 days history
        if len(historical) < 14:
            return []

        forecasts  = []
        today      = timezone.now().date()

        for i in range(1, days + 1):
            target_date = today + timedelta(days=i)
            weekday     = target_date.weekday()

            # Day-of-week average
            dow_avg    = self._day_of_week_average(historical, weekday)

            # Trend component
            trend      = self._calculate_trend(historical)

            # Combined prediction
            predicted  = max(0, round(dow_avg + (trend * i), 0))

            # Confidence interval (±20%)
            margin     = max(1, round(predicted * 0.20))

            forecasts.append({
                'date':      str(target_date),
                'day_name':  target_date.strftime('%A'),
                'predicted': int(predicted),
                'lower':     max(0, int(predicted - margin)),
                'upper':     int(predicted + margin),
                'is_weekend':weekday >= 5,
                'is_high':   predicted > dow_avg * 1.3,
            })

        cache.set(f'forecast:{days}', forecasts, timeout=self.CACHE_TTL)
        return forecasts

    def forecast_hourly(self) -> list:
        """Today-এর hourly volume forecast"""
        historical = self._get_historical_hourly(days=30)
        today_dow  = timezone.now().weekday()
        forecasts  = []

        for hour in range(0, 24):
            avg = self._hour_of_day_average(historical, today_dow, hour)
            forecasts.append({
                'hour':       hour,
                'hour_label': f'{hour:02d}:00',
                'predicted':  max(0, round(avg, 1)),
                'is_peak':    avg > self._overall_hourly_avg(historical) * 1.5,
            })

        return forecasts

    # ──────────────────────────────────────────
    # STAFFING RECOMMENDATIONS
    # ──────────────────────────────────────────
    def get_staffing_recommendation(self) -> dict:
        """
        Recommended agent count per day/shift।
        Based on predicted volume।
        """
        forecast   = self.forecast_volume(days=7)
        TICKETS_PER_AGENT_DAY = 15  # Average tickets an agent handles per day

        recommendations = []
        for day in forecast:
            predicted = day['predicted']
            agents_needed = math.ceil(predicted / TICKETS_PER_AGENT_DAY)
            agents_needed = max(2, min(agents_needed, 20))  # Min 2, Max 20

            recommendations.append({
                'date':           day['date'],
                'day_name':       day['day_name'],
                'predicted_volume':day['predicted'],
                'agents_needed':  agents_needed,
                'shift_breakdown': {
                    'morning':   math.ceil(agents_needed * 0.40),   # 9AM-2PM
                    'afternoon': math.ceil(agents_needed * 0.35),   # 2PM-6PM
                    'evening':   math.ceil(agents_needed * 0.25),   # 6PM-10PM
                },
            })

        return {
            'period_days':   7,
            'schedule':      recommendations,
            'avg_daily':     round(sum(d['predicted'] for d in forecast) / len(forecast), 0) if forecast else 0,
            'peak_day':      max(forecast, key=lambda x: x['predicted'])['day_name'] if forecast else None,
            'generated_at':  timezone.now().isoformat(),
        }

    # ──────────────────────────────────────────
    # TRENDS
    # ──────────────────────────────────────────
    def get_trends(self) -> dict:
        """Volume + resolution + CSAT trends"""
        historical = self._get_historical_daily(days=30)
        if not historical:
            return {}

        # Week over week
        this_week = sum(d['count'] for d in historical[-7:]) if len(historical) >= 7 else 0
        last_week = sum(d['count'] for d in historical[-14:-7]) if len(historical) >= 14 else 0
        wow_change= round((this_week - last_week) / last_week * 100, 1) if last_week else 0

        # Month over month
        this_month= sum(d['count'] for d in historical[-30:])
        last_month= sum(d['count'] for d in historical[-60:-30]) if len(historical) >= 60 else this_month
        mom_change= round((this_month - last_month) / last_month * 100, 1) if last_month else 0

        # Peak hours
        hourly   = self._get_historical_hourly(days=30)
        peak_hrs = self._find_peak_hours(hourly)

        # Category trends
        cat_trends = self._get_category_trends()

        return {
            'week_over_week':   {'change_pct': wow_change, 'this_week': this_week, 'last_week': last_week},
            'month_over_month': {'change_pct': mom_change, 'this_month': this_month, 'last_month': last_month},
            'peak_hours':       peak_hrs,
            'category_trends':  cat_trends,
            'daily_avg':        round(sum(d['count'] for d in historical) / len(historical), 1),
            'trend_direction':  'increasing' if wow_change > 5 else 'decreasing' if wow_change < -5 else 'stable',
        }

    def get_anomalies(self) -> list:
        """Unusual spikes detect করো"""
        historical = self._get_historical_daily(days=30)
        if not historical:
            return []

        values   = [d['count'] for d in historical]
        mean     = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev  = math.sqrt(variance)

        anomalies = []
        for item in historical:
            z_score = (item['count'] - mean) / std_dev if std_dev > 0 else 0
            if abs(z_score) > 2:  # More than 2 standard deviations
                anomalies.append({
                    'date':    str(item['date']),
                    'count':   item['count'],
                    'z_score': round(z_score, 2),
                    'type':    'spike' if z_score > 0 else 'drop',
                    'severity':'high' if abs(z_score) > 3 else 'medium',
                })

        return sorted(anomalies, key=lambda x: abs(x['z_score']), reverse=True)[:10]

    # ──────────────────────────────────────────
    # HISTORICAL DATA FETCHERS
    # ──────────────────────────────────────────
    def _get_historical_daily(self, days: int) -> list:
        """Daily ticket counts for last N days"""
        cached = cache.get(f'hist_daily:{days}')
        if cached:
            return cached

        try:
            from api.support.models import SupportTicket
            from django.db.models import Count
            from django.db.models.functions import TruncDate

            since = timezone.now() - timedelta(days=days)
            data  = list(
                SupportTicket.objects.filter(created_at__gte=since)
                .annotate(date=TruncDate('created_at'))
                .values('date')
                .annotate(count=Count('id'))
                .order_by('date')
            )
            cache.set(f'hist_daily:{days}', data, timeout=3600)
            return data
        except Exception as e:
            logger.error(f'Historical daily data failed: {e}')
            return []

    def _get_historical_hourly(self, days: int) -> list:
        """Hourly ticket counts with day-of-week"""
        cached = cache.get(f'hist_hourly:{days}')
        if cached:
            return cached

        try:
            from api.support.models import SupportTicket
            from django.db.models import Count
            from django.db.models.functions import TruncHour

            since = timezone.now() - timedelta(days=days)
            data  = list(
                SupportTicket.objects.filter(created_at__gte=since)
                .annotate(hour=TruncHour('created_at'))
                .values('hour')
                .annotate(count=Count('id'))
                .order_by('hour')
            )
            cache.set(f'hist_hourly:{days}', data, timeout=3600)
            return data
        except Exception as e:
            logger.error(f'Historical hourly data failed: {e}')
            return []

    def _get_category_trends(self) -> list:
        """Category volume trend"""
        try:
            from api.support.models import SupportTicket
            from django.db.models import Count

            since_7  = timezone.now() - timedelta(days=7)
            since_14 = timezone.now() - timedelta(days=14)

            this_week = {
                item['category']: item['count']
                for item in SupportTicket.objects.filter(created_at__gte=since_7)
                .values('category').annotate(count=Count('id'))
            }
            last_week = {
                item['category']: item['count']
                for item in SupportTicket.objects.filter(
                    created_at__gte=since_14, created_at__lt=since_7
                ).values('category').annotate(count=Count('id'))
            }

            trends = []
            for cat, count in this_week.items():
                prev    = last_week.get(cat, 0)
                change  = round((count - prev) / prev * 100, 1) if prev else 0
                trends.append({
                    'category':  cat,
                    'this_week': count,
                    'last_week': prev,
                    'change_pct':change,
                    'trend':     'up' if change > 10 else 'down' if change < -10 else 'stable',
                })

            return sorted(trends, key=lambda x: x['this_week'], reverse=True)
        except Exception:
            return []

    # ──────────────────────────────────────────
    # CALCULATION HELPERS
    # ──────────────────────────────────────────
    def _day_of_week_average(self, historical: list, weekday: int) -> float:
        """Specific weekday-এর average ticket count"""
        dow_counts = [
            item['count'] for item in historical
            if item['date'].weekday() == weekday
        ]
        if not dow_counts:
            overall = [item['count'] for item in historical]
            return sum(overall) / len(overall) if overall else 0

        # Weighted moving average (recent data has more weight)
        n      = len(dow_counts)
        weights= list(range(1, n + 1))
        total  = sum(w * v for w, v in zip(weights, dow_counts))
        return total / sum(weights)

    def _calculate_trend(self, historical: list) -> float:
        """Linear trend slope (tickets per day)"""
        if len(historical) < 7:
            return 0.0

        recent = historical[-14:]  # Last 2 weeks
        n      = len(recent)
        x_vals = list(range(n))
        y_vals = [item['count'] for item in recent]

        # Linear regression slope
        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n
        num    = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        den    = sum((x - x_mean) ** 2 for x in x_vals)

        return num / den if den != 0 else 0.0

    def _hour_of_day_average(self, hourly: list, weekday: int, hour: int) -> float:
        """Specific hour + weekday average"""
        matching = [
            item['count'] for item in hourly
            if item['hour'].weekday() == weekday and item['hour'].hour == hour
        ]
        return sum(matching) / len(matching) if matching else 0.0

    def _overall_hourly_avg(self, hourly: list) -> float:
        if not hourly:
            return 0
        return sum(item['count'] for item in hourly) / len(hourly)

    def _find_peak_hours(self, hourly: list) -> list:
        """Most busy hours"""
        hour_totals = {}
        for item in hourly:
            h = item['hour'].hour
            hour_totals[h] = hour_totals.get(h, 0) + item['count']

        sorted_hours = sorted(hour_totals.items(), key=lambda x: x[1], reverse=True)
        return [
            {'hour': h, 'hour_label': f'{h:02d}:00', 'total': count}
            for h, count in sorted_hours[:5]
        ]


# Singleton
predictive_analytics = PredictiveAnalytics()