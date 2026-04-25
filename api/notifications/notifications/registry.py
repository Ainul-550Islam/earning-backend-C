# earning_backend/api/notifications/registry.py
"""
Registry — Central notification type and template registry.
Maps notification_type strings to their default templates, channels, and priorities.
"""
import logging
from typing import Dict, Optional
logger = logging.getLogger(__name__)


class NotificationTypeRegistry:
    """Registry mapping notification types to their default config."""

    def __init__(self):
        self._types: Dict[str, dict] = {}
        self._register_defaults()

    def register(self, notification_type: str, default_channel: str = 'in_app',
                 default_priority: str = 'medium', template_name: str = '',
                 send_push: bool = False, send_email: bool = False, send_sms: bool = False):
        self._types[notification_type] = {
            'channel': default_channel, 'priority': default_priority,
            'template_name': template_name, 'send_push': send_push,
            'send_email': send_email, 'send_sms': send_sms,
        }

    def get(self, notification_type: str) -> Optional[dict]:
        return self._types.get(notification_type)

    def get_default_channel(self, notification_type: str) -> str:
        return self._types.get(notification_type, {}).get('channel', 'in_app')

    def get_default_priority(self, notification_type: str) -> str:
        return self._types.get(notification_type, {}).get('priority', 'medium')

    def all_types(self) -> list:
        return list(self._types.keys())

    def _register_defaults(self):
        """Register all default notification type configs."""
        configs = [
            # (type, channel, priority, push, email, sms)
            ('withdrawal_success', 'in_app', 'high', True, True, False),
            ('withdrawal_approved', 'in_app', 'high', True, False, False),
            ('withdrawal_rejected', 'in_app', 'high', True, True, False),
            ('withdrawal_failed', 'in_app', 'high', True, False, False),
            ('deposit_success', 'in_app', 'high', True, True, False),
            ('wallet_credited', 'in_app', 'medium', False, False, False),
            ('low_balance', 'in_app', 'medium', True, False, False),
            ('task_approved', 'in_app', 'high', True, False, False),
            ('task_rejected', 'in_app', 'medium', False, False, False),
            ('task_completed', 'in_app', 'medium', False, False, False),
            ('offer_completed', 'in_app', 'high', True, False, False),
            ('kyc_approved', 'in_app', 'high', True, True, False),
            ('kyc_rejected', 'in_app', 'high', True, True, False),
            ('kyc_submitted', 'in_app', 'medium', False, False, False),
            ('referral_completed', 'in_app', 'high', True, False, False),
            ('referral_reward', 'in_app', 'high', True, False, False),
            ('level_up', 'in_app', 'high', True, False, False),
            ('achievement_unlocked', 'in_app', 'high', True, False, False),
            ('fraud_detected', 'in_app', 'urgent', True, True, True),
            ('account_suspended', 'in_app', 'critical', True, True, False),
            ('login_new_device', 'in_app', 'high', True, True, False),
            ('daily_reward', 'in_app', 'medium', True, False, False),
            ('streak_reward', 'in_app', 'high', True, False, False),
            ('announcement', 'in_app', 'low', False, False, False),
            ('system_update', 'in_app', 'low', False, False, False),
        ]
        for cfg in configs:
            ntype, channel, priority = cfg[0], cfg[1], cfg[2]
            push, email, sms = cfg[3], cfg[4], cfg[5]
            self.register(ntype, channel, priority, send_push=push, send_email=email, send_sms=sms)


# Singleton
notification_type_registry = NotificationTypeRegistry()
