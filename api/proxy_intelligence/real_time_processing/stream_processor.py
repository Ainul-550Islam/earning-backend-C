"""Stream Processor — processes IP events in real-time."""
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

class StreamProcessor:
    """
    Processes a stream of IP events (clicks, logins, API calls) in real-time.
    Results are cached and thresholds trigger immediate alerts.
    """
    def __init__(self, tenant=None):
        self.tenant = tenant

    def process_event(self, event: dict) -> dict:
        """
        event = {
            'type': 'login|click|api_call|offer_complete',
            'ip_address': '...',
            'user_id': ...,
            'timestamp': '...',
            'metadata': {...}
        }
        """
        ip = event.get('ip_address', '')
        event_type = event.get('type', 'unknown')

        # Velocity check
        from ..services import VelocityService
        vel = VelocityService.record_and_check(
            ip_address=ip,
            action_type=event_type,
            tenant=self.tenant,
        )

        # Real-time score
        from .real_time_scorer import RealTimeScorer
        score = RealTimeScorer(ip, tenant=self.tenant).score_request()

        result = {
            'event_type': event_type,
            'ip_address': ip,
            'risk_score': score.get('risk_score', 0),
            'action': score.get('action', 'allow'),
            'velocity_exceeded': vel.exceeded,
            'should_block': score.get('is_blocked', False),
        }

        # Trigger alert for critical events
        if score.get('risk_score', 0) >= 81:
            from ..analytics_reporting.real_time_alert import RealTimeAlertGenerator
            RealTimeAlertGenerator(self.tenant).alert_critical_ip(
                ip, score['risk_score'], score.get('flags', [])
            )

        return result
