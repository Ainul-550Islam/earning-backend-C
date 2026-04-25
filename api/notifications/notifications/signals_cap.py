# earning_backend/api/notifications/signals_cap.py
"""
Signals CAP (Capacity) — Signal connection manager and signal registry.

"CAP" = Capacity layer that:
  1. Tracks all connected signals (avoid duplicate connections)
  2. Provides connect_all() / disconnect_all() helpers
  3. Manages signal connection lifecycle
  4. Called from apps.py ready()
"""

import logging
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import Signal

from .events import (
    notification_sent, notification_delivered, notification_read,
    notification_failed, notification_deleted, notification_expired,
    notification_clicked, device_token_registered, device_token_deactivated,
    push_token_invalid, campaign_started, campaign_completed,
    user_opted_out, user_resubscribed, fatigue_threshold_reached,
    integration_event, integration_error, health_status_changed,
)
from .receivers import (
    on_notification_post_save, on_notification_read,
    on_in_app_message_post_save, on_opt_out_post_save,
    on_fatigue_post_save, on_device_token_post_save,
    on_integration_event, on_integration_error,
)

logger = logging.getLogger(__name__)

_CONNECTED = False  # Prevent double-connection


def connect_all():
    """
    Connect all receivers to their signals.
    Safe to call multiple times — only connects once.
    Called from notifications/apps.py ready().
    """
    global _CONNECTED
    if _CONNECTED:
        logger.debug('signals_cap: already connected — skipping')
        return

    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # ── Core notification signals ────────────────────────────────
        try:
            from notifications.models import Notification
            post_save.connect(
                on_notification_post_save,
                sender=Notification,
                weak=False,
                dispatch_uid='notifications.notification.post_save',
            )
        except Exception as exc:
            logger.warning(f'signals_cap Notification: {exc}')

        # ── InAppMessage signals ─────────────────────────────────────
        try:
            from notifications.models.channel import InAppMessage
            post_save.connect(
                on_in_app_message_post_save,
                sender=InAppMessage,
                weak=False,
                dispatch_uid='notifications.inappmessage.post_save',
            )
        except Exception as exc:
            logger.warning(f'signals_cap InAppMessage: {exc}')

        # ── OptOutTracking signals ───────────────────────────────────
        try:
            from notifications.models.analytics import OptOutTracking
            post_save.connect(
                on_opt_out_post_save,
                sender=OptOutTracking,
                weak=False,
                dispatch_uid='notifications.optout.post_save',
            )
        except Exception as exc:
            logger.warning(f'signals_cap OptOutTracking: {exc}')

        # ── NotificationFatigue signals ──────────────────────────────
        try:
            from notifications.models.analytics import NotificationFatigue
            post_save.connect(
                on_fatigue_post_save,
                sender=NotificationFatigue,
                weak=False,
                dispatch_uid='notifications.fatigue.post_save',
            )
        except Exception as exc:
            logger.warning(f'signals_cap NotificationFatigue: {exc}')

        # ── DeviceToken signals ──────────────────────────────────────
        try:
            from notifications.models import DeviceToken
            post_save.connect(
                on_device_token_post_save,
                sender=DeviceToken,
                weak=False,
                dispatch_uid='notifications.devicetoken.post_save',
            )
        except Exception as exc:
            logger.warning(f'signals_cap DeviceToken: {exc}')

        # ── Custom integration signals ───────────────────────────────
        integration_event.connect(
            on_integration_event,
            weak=False,
            dispatch_uid='notifications.integration.event',
        )
        integration_error.connect(
            on_integration_error,
            weak=False,
            dispatch_uid='notifications.integration.error',
        )

        _CONNECTED = True
        logger.info('signals_cap: all signals connected ✅')

    except Exception as exc:
        logger.error(f'signals_cap.connect_all: {exc}')


def disconnect_all():
    """Disconnect all notification signals. Useful in tests."""
    global _CONNECTED

    try:
        from notifications.models import Notification, DeviceToken
        from notifications.models.channel import InAppMessage
        from notifications.models.analytics import OptOutTracking, NotificationFatigue

        post_save.disconnect(dispatch_uid='notifications.notification.post_save')
        post_save.disconnect(dispatch_uid='notifications.inappmessage.post_save')
        post_save.disconnect(dispatch_uid='notifications.optout.post_save')
        post_save.disconnect(dispatch_uid='notifications.fatigue.post_save')
        post_save.disconnect(dispatch_uid='notifications.devicetoken.post_save')
        integration_event.disconnect(dispatch_uid='notifications.integration.event')
        integration_error.disconnect(dispatch_uid='notifications.integration.error')

    except Exception as exc:
        logger.warning(f'signals_cap.disconnect_all: {exc}')

    _CONNECTED = False
    logger.debug('signals_cap: all signals disconnected')


def is_connected() -> bool:
    return _CONNECTED


def list_connected_signals() -> dict:
    """Return a summary of all registered signal connections."""
    return {
        'notification_post_save': 'on_notification_post_save',
        'in_app_message_post_save': 'on_in_app_message_post_save',
        'opt_out_post_save': 'on_opt_out_post_save',
        'fatigue_post_save': 'on_fatigue_post_save',
        'device_token_post_save': 'on_device_token_post_save',
        'integration_event': 'on_integration_event',
        'integration_error': 'on_integration_error',
        'all_connected': _CONNECTED,
    }
