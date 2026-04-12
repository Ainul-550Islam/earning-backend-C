"""WebSocket Notifier — sends real-time alerts via Django Channels."""
import logging, json
logger = logging.getLogger(__name__)

class WebSocketNotifier:
    """
    Sends real-time notifications to connected admin WebSocket clients.
    Requires Django Channels: pip install channels channels-redis
    """

    GROUP_ADMIN_ALERTS = 'pi_admin_alerts'

    @classmethod
    def notify_high_risk(cls, ip_address: str, risk_score: int, flags: list):
        cls._send(cls.GROUP_ADMIN_ALERTS, {
            'type': 'high_risk_ip',
            'ip_address': ip_address,
            'risk_score': risk_score,
            'flags': flags,
        })

    @classmethod
    def notify_fraud(cls, ip_address: str, fraud_type: str, user_id: int = None):
        cls._send(cls.GROUP_ADMIN_ALERTS, {
            'type': 'fraud_detected',
            'ip_address': ip_address,
            'fraud_type': fraud_type,
            'user_id': user_id,
        })

    @classmethod
    def notify_blacklist(cls, ip_address: str, reason: str):
        cls._send(cls.GROUP_ADMIN_ALERTS, {
            'type': 'ip_blacklisted',
            'ip_address': ip_address,
            'reason': reason,
        })

    @classmethod
    def _send(cls, group: str, data: dict):
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            layer = get_channel_layer()
            if layer:
                async_to_sync(layer.group_send)(group, {
                    'type': 'pi.alert',
                    'message': json.dumps(data),
                })
        except Exception as e:
            logger.debug(f"WebSocket notify failed: {e}")
