# api/offer_inventory/optimization_scale/real_time_streaming.py
"""Real-Time Streaming — SSE and Redis pub/sub for live dashboard updates."""
import json
import time
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class RealTimeStreamingService:
    """Server-Sent Events and Redis pub/sub for real-time data."""

    @staticmethod
    def live_stats_generator(tenant=None):
        """
        SSE generator for live platform stats.

        Usage in view:
            from django.http import StreamingHttpResponse
            response = StreamingHttpResponse(
                RealTimeStreamingService.live_stats_generator(),
                content_type='text/event-stream',
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response
        """
        while True:
            try:
                from api.offer_inventory.reporting_audit.admin_dashboard_stats import AdminDashboardStats
                stats   = AdminDashboardStats.get_live_stats(tenant=tenant)
                payload = json.dumps(stats, default=str)
                yield f'data: {payload}\n\n'
            except Exception as e:
                yield f'data: {{"error": "{str(e)}"}}\n\n'
            time.sleep(30)

    @staticmethod
    def publish_event(channel: str, event_type: str, data: dict):
        """Publish event to Redis pub/sub channel."""
        try:
            import redis
            from django.conf import settings
            r       = redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
            payload = json.dumps({
                'type'     : event_type,
                'data'     : data,
                'timestamp': timezone.now().isoformat(),
            }, default=str)
            r.publish(f'offer_inventory:{channel}', payload)
        except Exception as e:
            logger.debug(f'Pub/sub publish error: {e}')

    @staticmethod
    def subscribe(channel: str):
        """Subscribe to a Redis pub/sub channel."""
        try:
            import redis
            from django.conf import settings
            r      = redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
            pubsub = r.pubsub()
            pubsub.subscribe(f'offer_inventory:{channel}')
            return pubsub
        except Exception as e:
            logger.error(f'Subscribe error: {e}')
            return None

    @staticmethod
    def fire_conversion_event(conversion):
        """Broadcast new conversion event."""
        RealTimeStreamingService.publish_event('conversions', 'new_conversion', {
            'offer_id'     : str(conversion.offer_id),
            'payout'       : str(conversion.payout_amount),
            'country'      : conversion.country_code,
        })

    @staticmethod
    def fire_fraud_alert(user_id, fraud_type: str, score: float):
        """Broadcast fraud detection event."""
        RealTimeStreamingService.publish_event('fraud', 'fraud_detected', {
            'user_id'   : str(user_id),
            'fraud_type': fraud_type,
            'score'     : score,
        })

    @staticmethod
    def fire_withdrawal_event(withdrawal):
        """Broadcast withdrawal request event."""
        RealTimeStreamingService.publish_event('withdrawals', 'new_withdrawal', {
            'amount': str(withdrawal.amount),
            'status': withdrawal.status,
        })
