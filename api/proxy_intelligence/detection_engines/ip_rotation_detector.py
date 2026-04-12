"""IP Rotation Detector — detects rapid IP changes per user/session."""
import logging
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
logger = logging.getLogger(__name__)

class IPRotationDetector:
    """
    Detects if a user/session is rotating IP addresses rapidly,
    a common technique used by bots and fraud tools.
    """
    def __init__(self, user_id: int = None, session_id: str = ''):
        self.user_id = user_id
        self.session_id = session_id
        self.key = f"pi:ip_rotation:{'u'+str(user_id) if user_id else 's'+session_id}"

    def record_ip(self, ip_address: str) -> dict:
        """Record an IP and check for rotation."""
        history = cache.get(self.key, [])
        if ip_address not in history:
            history.append(ip_address)
        cache.set(self.key, history[-20:], 3600)

        rotation_detected = len(set(history)) >= 3
        unique_ips = len(set(history))

        if rotation_detected:
            self._save_anomaly(history, unique_ips)

        return {
            'ip_address': ip_address,
            'rotation_detected': rotation_detected,
            'unique_ips_in_window': unique_ips,
            'ip_history': history,
            'confidence': min(unique_ips * 0.2, 1.0),
        }

    def _save_anomaly(self, history: list, unique_count: int):
        try:
            from ..models import AnomalyDetectionLog
            AnomalyDetectionLog.objects.create(
                ip_address=history[-1],
                anomaly_type='pattern_deviation',
                description=f'IP rotation detected: {unique_count} unique IPs',
                anomaly_score=min(unique_count * 0.2, 1.0),
                evidence={'ip_history': history, 'unique_count': unique_count},
            )
        except Exception as e:
            logger.debug(f"IP rotation anomaly save failed: {e}")
