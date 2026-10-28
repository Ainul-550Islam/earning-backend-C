"""
api/support/reports/volume_forecast.py
FILE 52/70 — Volume Forecast Report (wrapper)
"""
import logging
logger = logging.getLogger(__name__)

class VolumeForecastReport:
    def generate(self, forecast_days: int = 7, history_days: int = 90) -> dict:
        from api.support.analytics.predictive_analytics import predictive_analytics
        return {
            'forecast':         predictive_analytics.forecast_volume(days=forecast_days),
            'staffing':         predictive_analytics.get_staffing_recommendation(),
            'trends':           predictive_analytics.get_trends(),
            'anomalies':        predictive_analytics.get_anomalies(),
            'hourly_today':     predictive_analytics.forecast_hourly(),
        }

volume_forecast_report = VolumeForecastReport()