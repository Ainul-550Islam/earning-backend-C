# api/offer_inventory/maintenance_logs/emergency_shutdown.py
"""Emergency Shutdown — One-click platform feature disable."""
import logging
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

SHUTDOWN_CACHE_KEY = 'emergency_shutdown:state'


class EmergencyShutdown:
    """Gracefully disable platform features without downtime."""

    @classmethod
    def activate(cls, reason: str, activated_by=None,
                  disable_offers: bool = True,
                  disable_conversions: bool = True,
                  disable_withdrawals: bool = True) -> dict:
        """Activate emergency shutdown mode."""
        from api.offer_inventory.repository import FeatureFlagRepository

        disabled = []
        if disable_offers:
            FeatureFlagRepository.set_feature('offer_wall', False, user=activated_by)
            disabled.append('offer_wall')
        if disable_conversions:
            FeatureFlagRepository.set_feature('conversions', False, user=activated_by)
            disabled.append('conversions')
        if disable_withdrawals:
            FeatureFlagRepository.set_feature('withdrawals', False, user=activated_by)
            disabled.append('withdrawals')

        state = {
            'active'       : True,
            'reason'       : reason,
            'activated_by' : str(activated_by.id) if activated_by else 'system',
            'at'           : timezone.now().isoformat(),
            'disabled'     : disabled,
        }
        cache.set(SHUTDOWN_CACHE_KEY, state, 86400)

        logger.critical(
            f'EMERGENCY SHUTDOWN ACTIVATED: {reason} | '
            f'disabled={disabled} | by={state["activated_by"]}'
        )

        # Alert via Slack + Email
        try:
            from api.offer_inventory.notifications.slack_webhook import SlackNotifier
            from api.offer_inventory.notifications.email_alert_system import EmailAlertSystem
            SlackNotifier().alert_system_error(f'EMERGENCY SHUTDOWN: {reason}')
            EmailAlertSystem.send_system_error_alert(f'EMERGENCY SHUTDOWN: {reason}')
        except Exception as e:
            logger.error(f'Shutdown alert error: {e}')

        return {'activated': True, 'disabled': disabled, 'reason': reason}

    @classmethod
    def deactivate(cls, restored_by=None) -> dict:
        """Restore normal operations."""
        from api.offer_inventory.repository import FeatureFlagRepository

        for feature in ['offer_wall', 'conversions', 'withdrawals']:
            FeatureFlagRepository.set_feature(feature, True, user=restored_by)

        cache.delete(SHUTDOWN_CACHE_KEY)
        logger.info('Emergency shutdown deactivated — normal operations restored.')
        return {
            'deactivated': True,
            'restored_by': str(restored_by.id) if restored_by else 'system',
            'at'         : timezone.now().isoformat(),
        }

    @classmethod
    def get_status(cls) -> dict:
        """Get current shutdown status."""
        state = cache.get(SHUTDOWN_CACHE_KEY)
        return state or {'active': False}

    @classmethod
    def is_active(cls) -> bool:
        """Quick check if shutdown is active."""
        return bool(cache.get(SHUTDOWN_CACHE_KEY, {}).get('active', False))
