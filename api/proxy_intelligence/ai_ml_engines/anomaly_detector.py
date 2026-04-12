"""
Anomaly Detector
================
Detects statistical anomalies in user behavior patterns using ML.
"""
import logging
import statistics
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detects behavioral anomalies using statistical methods.
    Uses Z-score and IQR approaches for simple, interpretable anomaly detection.
    """

    def __init__(self, user=None, ip_address: str = ''):
        self.user = user
        self.ip_address = ip_address

    def detect_velocity_anomaly(self, action_type: str, window_hours: int = 1) -> dict:
        """Detect if current request rate is anomalous vs historical baseline."""
        if not self.user:
            return {'anomaly_detected': False, 'type': 'velocity_spike'}

        cache_key = f"pi:velocity_history:{self.user.pk}:{action_type}"
        history = cache.get(cache_key, [])
        current_count = self._get_current_count(action_type, window_hours)

        anomaly_detected = False
        z_score = 0.0
        if len(history) >= 5:
            mean = statistics.mean(history)
            stdev = statistics.stdev(history) or 1
            z_score = (current_count - mean) / stdev
            anomaly_detected = abs(z_score) > 2.5  # 2.5 sigma threshold

        # Update history
        history.append(current_count)
        if len(history) > 30:
            history = history[-30:]
        cache.set(cache_key, history, 86400)

        if anomaly_detected:
            self._save_anomaly('velocity_spike', {
                'action_type': action_type,
                'current_count': current_count,
                'z_score': z_score,
                'window_hours': window_hours,
            }, z_score)

        return {
            'anomaly_detected': anomaly_detected,
            'type': 'velocity_spike',
            'z_score': round(z_score, 3),
            'current_count': current_count,
        }

    def detect_geo_anomaly(self, current_country: str) -> dict:
        """Detect if user logged in from an unusual country."""
        if not self.user:
            return {'anomaly_detected': False, 'type': 'geo_jump'}

        cache_key = f"pi:geo_history:{self.user.pk}"
        country_history = cache.get(cache_key, [])

        anomaly_detected = False
        if country_history and current_country not in country_history[-5:]:
            anomaly_detected = True
            self._save_anomaly('geo_jump', {
                'current_country': current_country,
                'recent_countries': country_history[-5:],
            }, 0.9)

        if current_country not in country_history:
            country_history.append(current_country)
            cache.set(cache_key, country_history[-20:], 86400 * 30)

        return {
            'anomaly_detected': anomaly_detected,
            'type': 'geo_jump',
            'current_country': current_country,
        }

    def detect_time_anomaly(self, hour_of_day: int) -> dict:
        """Detect if activity time is unusual for this user."""
        if not self.user:
            return {'anomaly_detected': False, 'type': 'time_anomaly'}

        cache_key = f"pi:time_history:{self.user.pk}"
        hour_history = cache.get(cache_key, [])

        anomaly_detected = False
        if len(hour_history) >= 10:
            mean = statistics.mean(hour_history)
            stdev = statistics.stdev(hour_history) or 3
            z_score = abs(hour_of_day - mean) / stdev
            if z_score > 3:
                anomaly_detected = True
                self._save_anomaly('time_anomaly', {
                    'hour': hour_of_day, 'z_score': z_score
                }, z_score / 10)

        hour_history.append(hour_of_day)
        cache.set(cache_key, hour_history[-30:], 86400 * 30)

        return {'anomaly_detected': anomaly_detected, 'type': 'time_anomaly'}

    def _get_current_count(self, action_type: str, window_hours: int) -> int:
        cache_key = f"pi:action_count:{self.user.pk}:{action_type}:{window_hours}h"
        return cache.get(cache_key, 0)

    def _save_anomaly(self, anomaly_type: str, evidence: dict, score: float):
        try:
            from ..models import AnomalyDetectionLog
            AnomalyDetectionLog.objects.create(
                user=self.user,
                ip_address=self.ip_address or '0.0.0.0',
                anomaly_type=anomaly_type,
                anomaly_score=min(score, 1.0),
                evidence=evidence,
                description=f"Anomaly detected: {anomaly_type}",
            )
        except Exception as e:
            logger.error(f"Failed to save anomaly: {e}")

    def run_all_checks(self, current_country: str = '', current_hour: int = 12) -> dict:
        """Run all anomaly checks and return combined result."""
        results = {
            'velocity': self.detect_velocity_anomaly('api_call'),
            'geo': self.detect_geo_anomaly(current_country) if current_country else {},
            'time': self.detect_time_anomaly(current_hour),
        }
        any_anomaly = any(r.get('anomaly_detected') for r in results.values() if r)
        return {
            'anomaly_detected': any_anomaly,
            'checks': results,
        }
