# earning_backend/api/notifications/services/providers/FCMProvider.py
"""
FCMProvider — Firebase Cloud Messaging push notification provider.

Handles:
  - Single-device token sends (messaging.Message)
  - Multicast sends (up to 500 tokens per batch via messaging.MulticastMessage)
  - Token validation / refresh detection
  - Full Android + APNs + WebPush config building

Settings required (add to Django settings.py):
    FIREBASE_CREDENTIALS  — path to serviceAccountKey.json  OR dict with creds
    FIREBASE_APP_NAME     — (optional) name for the firebase_admin App instance
                            useful when multiple apps are initialised
    APNS_TOPIC            — (optional) iOS bundle ID, e.g. "com.yourapp.app"
"""

import json
import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy Firebase initialisation
# ---------------------------------------------------------------------------
_firebase_app = None


def _get_firebase_app():
    """
    Return (and lazily initialise) the firebase_admin App.
    Re-uses an existing app if already initialised.
    """
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_source = getattr(settings, 'FIREBASE_CREDENTIALS', None)
        if not cred_source:
            logger.warning('FCMProvider: FIREBASE_CREDENTIALS not configured — FCM disabled.')
            return None

        app_name = getattr(settings, 'FIREBASE_APP_NAME', '[DEFAULT]')

        # Accept either a file path (str) or an already-loaded dict
        if isinstance(cred_source, str):
            cred = credentials.Certificate(cred_source)
        elif isinstance(cred_source, dict):
            cred = credentials.Certificate(cred_source)
        else:
            logger.error('FCMProvider: FIREBASE_CREDENTIALS must be a file path or dict.')
            return None

        try:
            _firebase_app = firebase_admin.get_app(app_name)
        except ValueError:
            _firebase_app = firebase_admin.initialize_app(cred, name=app_name)

        logger.info('FCMProvider: Firebase app initialised successfully.')
        return _firebase_app

    except Exception as exc:
        logger.error(f'FCMProvider: Failed to initialise Firebase — {exc}')
        return None


# ---------------------------------------------------------------------------
# FCMProvider class
# ---------------------------------------------------------------------------

class FCMProvider:
    """
    Thin wrapper around firebase_admin.messaging that exposes a consistent
    send / send_multicast interface used by NotificationDispatcher.
    """

    # FCM error codes that mean the token is permanently invalid
    INVALID_TOKEN_ERRORS = {
        'registration-token-not-registered',
        'invalid-registration-token',
        'invalid-argument',
        'mismatched-credential',
    }

    def __init__(self):
        self._app = _get_firebase_app()
        self._available = self._app is not None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if Firebase was initialised successfully."""
        return self._available

    def send(self, token: str, notification, extra_data: Optional[Dict] = None) -> Dict:
        """
        Send a push notification to a single FCM registration token.

        Args:
            token:         FCM registration token string.
            notification:  Core Notification model instance.
            extra_data:    Optional extra key-value pairs to include in the
                           FCM data payload.

        Returns:
            Dict with keys: success (bool), provider (str), message_id (str),
            error (str), is_invalid_token (bool).
        """
        if not self._available:
            return self._unavailable_response()

        try:
            from firebase_admin import messaging

            message = self._build_message(token, notification, extra_data or {})
            response = messaging.send(message, app=self._app)

            return {
                'success': True,
                'provider': 'fcm',
                'message_id': response,
                'is_invalid_token': False,
                'error': '',
            }

        except Exception as exc:
            error_str = str(exc)
            is_invalid = self._is_invalid_token_error(error_str)
            logger.warning(f'FCMProvider.send failed for token …{token[-6:]}: {error_str}')
            return {
                'success': False,
                'provider': 'fcm',
                'message_id': '',
                'is_invalid_token': is_invalid,
                'error': error_str,
            }

    def send_multicast(
        self,
        tokens: List[str],
        notification,
        extra_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Send the same notification to up to 500 FCM tokens at once.

        Returns:
            Dict with keys: success (bool), provider, total, success_count,
            failure_count, invalid_tokens (list), responses (list of dicts).
        """
        if not self._available:
            return {**self._unavailable_response(), 'total': len(tokens),
                    'success_count': 0, 'failure_count': len(tokens),
                    'invalid_tokens': [], 'responses': []}

        if not tokens:
            return {
                'success': False,
                'provider': 'fcm',
                'error': 'No tokens provided',
                'total': 0,
                'success_count': 0,
                'failure_count': 0,
                'invalid_tokens': [],
                'responses': [],
            }

        # FCM multicast limit is 500 tokens per call
        BATCH_SIZE = 500
        all_responses = []
        total_success = 0
        total_failure = 0
        invalid_tokens: List[str] = []

        try:
            from firebase_admin import messaging

            for i in range(0, len(tokens), BATCH_SIZE):
                batch = tokens[i: i + BATCH_SIZE]
                mm = self._build_multicast_message(batch, notification, extra_data or {})
                batch_response = messaging.send_each_for_multicast(mm, app=self._app)

                for idx, resp in enumerate(batch_response.responses):
                    token = batch[idx]
                    if resp.success:
                        total_success += 1
                        all_responses.append({
                            'token': token[-6:] + '…',
                            'success': True,
                            'message_id': resp.message_id,
                        })
                    else:
                        total_failure += 1
                        err_str = str(resp.exception) if resp.exception else 'unknown'
                        if self._is_invalid_token_error(err_str):
                            invalid_tokens.append(token)
                        all_responses.append({
                            'token': token[-6:] + '…',
                            'success': False,
                            'error': err_str,
                        })

        except Exception as exc:
            logger.error(f'FCMProvider.send_multicast failed: {exc}')
            return {
                'success': False,
                'provider': 'fcm',
                'error': str(exc),
                'total': len(tokens),
                'success_count': 0,
                'failure_count': len(tokens),
                'invalid_tokens': [],
                'responses': [],
            }

        return {
            'success': total_success > 0,
            'provider': 'fcm',
            'error': '',
            'total': len(tokens),
            'success_count': total_success,
            'failure_count': total_failure,
            'invalid_tokens': invalid_tokens,
            'responses': all_responses,
        }

    # ------------------------------------------------------------------
    def send_rich_push(self, token: str, notification, image_url: str = '',
                      action_buttons: list = None, **kwargs) -> Dict:
        """
        Send a Rich Push notification with image + action buttons.
        Supported: Android (FCM BigPicture) + iOS (APNs media attachment).

        action_buttons: [{'id': 'open', 'title': 'Open', 'url': '...'}, ...]
        """
        if not self._available:
            return self._unavailable_response()
        try:
            from firebase_admin import messaging
            extra = {'rich_push': 'true', 'image_url': image_url}
            if action_buttons:
                import json
                extra['action_buttons'] = json.dumps(action_buttons)

            android_notif = messaging.AndroidNotification(
                title=notification.title,
                body=notification.message,
                image=image_url or None,
                icon='default',
                color='#FF6B35',
                channel_id=getattr(settings, 'FCM_ANDROID_CHANNEL_ID', 'default'),
            )
            android_cfg = messaging.AndroidConfig(priority='high', notification=android_notif)

            apns_cfg = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(title=notification.title, body=notification.message),
                        sound='default',
                        mutable_content=True,  # Required for media attachment
                    ),
                ),
                fcm_options=messaging.APNSFCMOptions(image=image_url or None),
            )

            message = messaging.Message(
                notification=messaging.Notification(title=notification.title, body=notification.message, image=image_url or None),
                data={**self._build_data_payload(notification, extra), **extra},
                token=token,
                android=android_cfg,
                apns=apns_cfg,
            )
            response = messaging.send(message, app=self._app)
            return {'success': True, 'provider': 'fcm_rich', 'message_id': response, 'error': ''}
        except Exception as exc:
            return {'success': False, 'provider': 'fcm_rich', 'error': str(exc)}

    def send_silent_push(self, tokens: list, data: Dict) -> Dict:
        """
        Send a Silent Push (content-available=1) — wakes app in background.
        Used for: sync triggers, badge updates, data refresh.
        No visible notification shown to user.
        """
        if not self._available:
            return self._unavailable_response()
        try:
            from firebase_admin import messaging
            mm = messaging.MulticastMessage(
                data={k: str(v) for k, v in data.items()},
                tokens=tokens,
                android=messaging.AndroidConfig(priority='high'),
                apns=messaging.APNSConfig(
                    headers={'apns-priority': '5', 'apns-push-type': 'background'},
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(content_available=True)
                    ),
                ),
            )
            resp = messaging.send_each_for_multicast(mm, app=self._app)
            return {'success': resp.success_count > 0, 'provider': 'fcm_silent',
                    'success_count': resp.success_count, 'failure_count': resp.failure_count}
        except Exception as exc:
            return {'success': False, 'provider': 'fcm_silent', 'error': str(exc)}

    # Message builders
    # ------------------------------------------------------------------

    def _build_message(self, token: str, notification, extra_data: Dict):
        """Build a firebase_admin.messaging.Message for a single token."""
        from firebase_admin import messaging

        data_payload = self._build_data_payload(notification, extra_data)
        android_cfg = self._build_android_config(notification)
        apns_cfg = self._build_apns_config(notification)
        webpush_cfg = self._build_webpush_config(notification)

        return messaging.Message(
            notification=messaging.Notification(
                title=notification.title,
                body=notification.message,
                image=getattr(notification, 'image_url', None) or None,
            ),
            data=data_payload,
            token=token,
            android=android_cfg,
            apns=apns_cfg,
            webpush=webpush_cfg,
        )

    def _build_multicast_message(self, tokens: List[str], notification, extra_data: Dict):
        """Build a firebase_admin.messaging.MulticastMessage for batch send."""
        from firebase_admin import messaging

        data_payload = self._build_data_payload(notification, extra_data)
        android_cfg = self._build_android_config(notification)
        apns_cfg = self._build_apns_config(notification)
        webpush_cfg = self._build_webpush_config(notification)

        return messaging.MulticastMessage(
            notification=messaging.Notification(
                title=notification.title,
                body=notification.message,
                image=getattr(notification, 'image_url', None) or None,
            ),
            data=data_payload,
            tokens=tokens,
            android=android_cfg,
            apns=apns_cfg,
            webpush=webpush_cfg,
        )

    def _build_data_payload(self, notification, extra_data: Dict) -> Dict:
        """Build the FCM data dict (all values must be strings)."""
        is_high_priority = getattr(notification, 'is_high_priority', lambda: False)()
        payload = {
            'notification_id': str(notification.id),
            'type': str(getattr(notification, 'notification_type', '')),
            'priority': str(getattr(notification, 'priority', 'medium')),
            'action_url': str(getattr(notification, 'action_url', '') or ''),
            'deep_link': str(getattr(notification, 'deep_link', '') or ''),
            'created_at': notification.created_at.isoformat() if hasattr(notification, 'created_at') else '',
        }

        # Safely serialise metadata
        metadata = getattr(notification, 'metadata', {})
        if metadata:
            try:
                payload['metadata'] = json.dumps(metadata)
            except (TypeError, ValueError):
                payload['metadata'] = '{}'

        # Merge caller-supplied extras (string-cast for safety)
        for k, v in extra_data.items():
            payload[str(k)] = str(v)

        return payload

    # Sound mapping per notification type
    NOTIFICATION_SOUND_MAP = {
        'withdrawal_success': 'money_received',
        'withdrawal_failed':  'alert',
        'task_approved':      'success',
        'task_rejected':      'alert',
        'referral_reward':    'bonus',
        'level_up':           'level_up',
        'fraud_detected':     'urgent_alert',
        'kyc_approved':       'success',
        'offer_completed':    'coin',
        'daily_reward':       'reward',
        'streak_reward':      'streak',
        'achievement_unlocked': 'achievement',
        'low_balance':        'warning',
        'login_new_device':   'security',
    }

    def send_carousel_push(self, token: str, notification,
                            carousel_items: list, **kwargs) -> Dict:
        """
        Send a Carousel Push notification (image slideshow).
        carousel_items: [{'title': str, 'image_url': str, 'action_url': str}, ...]
        Max 10 items. Android only via custom data handling.

        Usage:
            fcm_provider.send_carousel_push(token, notification, [
                {'title': 'Offer 1', 'image_url': 'https://...', 'action_url': '...'},
                {'title': 'Offer 2', 'image_url': 'https://...', 'action_url': '...'},
            ])
        """
        if not self._available:
            return self._unavailable_response()
        try:
            from firebase_admin import messaging
            import json

            # Carousel data is passed via notification data payload
            # The client app must handle rendering the carousel
            data = {
                'notification_id': str(getattr(notification, 'pk', '')),
                'type': 'carousel',
                'carousel_items': json.dumps(carousel_items[:10]),
                'carousel_count': str(len(carousel_items[:10])),
                'title': notification.title,
                'message': notification.message,
                'action_url': getattr(notification, 'action_url', '') or '',
            }

            message = messaging.Message(
                data=data,
                token=token,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        title=notification.title,
                        body=notification.message,
                        image=carousel_items[0].get('image_url') if carousel_items else None,
                        channel_id=getattr(settings, 'FCM_ANDROID_CHANNEL_ID', 'default'),
                    )
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(
                                title=notification.title,
                                body=notification.message,
                            ),
                            mutable_content=True,
                        )
                    ),
                    fcm_options=messaging.APNSFCMOptions(
                        image=carousel_items[0].get('image_url') if carousel_items else None
                    ),
                ),
            )
            response = messaging.send(message, app=self._app)
            return {'success': True, 'provider': 'fcm_carousel',
                    'message_id': response, 'items': len(carousel_items), 'error': ''}
        except Exception as exc:
            return {'success': False, 'provider': 'fcm_carousel', 'error': str(exc)}

    def send_gif_push(self, token: str, notification, gif_url: str, **kwargs) -> Dict:
        """
        Send a push notification with an animated GIF.
        Note: Android shows the GIF; iOS shows the first frame.
        """
        if not self._available:
            return self._unavailable_response()
        # GIF push is essentially rich push with the gif_url as image
        return self.send_rich_push(token, notification, image_url=gif_url, **kwargs)

    def _get_notification_sound(self, notification) -> str:
        notif_type = getattr(notification, 'notification_type', '') or ''
        return self.NOTIFICATION_SOUND_MAP.get(notif_type, 'default')

    def _build_android_config(self, notification):
        """Build AndroidConfig."""
        from firebase_admin import messaging

        is_high_priority = getattr(notification, 'is_high_priority', lambda: False)()
        sound_enabled = getattr(notification, 'sound_enabled', True)
        group_id = getattr(notification, 'group_id', '') or None
        action_url = getattr(notification, 'action_url', '') or ''
        deep_link = getattr(notification, 'deep_link', '') or ''

        android_notif = messaging.AndroidNotification(
            title=notification.title,
            body=notification.message,
            icon=getattr(notification, 'icon_url', None) or 'default',
            color='#FF6B35',
            sound=self._get_notification_sound(notification) if sound_enabled else None,
            tag=group_id,
            click_action=action_url or deep_link or None,
            channel_id=getattr(settings, 'FCM_ANDROID_CHANNEL_ID', 'default'),
        )

        return messaging.AndroidConfig(
            priority='high' if is_high_priority else 'normal',
            ttl=timedelta(days=1),
            collapse_key=group_id,
            notification=android_notif,
        )

    def _build_apns_config(self, notification):
        """Build APNSConfig for iOS."""
        from firebase_admin import messaging

        is_high_priority = getattr(notification, 'is_high_priority', lambda: False)()
        sound_enabled = getattr(notification, 'sound_enabled', True)
        badge_count = getattr(notification, 'badge_count', None)
        group_id = getattr(notification, 'group_id', '') or None
        apns_topic = getattr(settings, 'APNS_TOPIC', 'com.example.app')

        return messaging.APNSConfig(
            headers={
                'apns-priority': '10' if is_high_priority else '5',
                'apns-topic': apns_topic,
            },
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    alert=messaging.ApsAlert(
                        title=notification.title,
                        body=notification.message,
                    ),
                    sound=self._get_notification_sound(notification) if sound_enabled else None,
                    badge=badge_count,
                    category=getattr(notification, 'notification_type', None),
                    thread_id=group_id,
                ),
            ),
        )

    def _build_webpush_config(self, notification):
        """Build WebpushConfig for browser push."""
        from firebase_admin import messaging

        icon_url = getattr(notification, 'icon_url', None) or ''
        action_url = getattr(notification, 'action_url', '') or ''

        webpush_notif = messaging.WebpushNotification(
            title=notification.title,
            body=notification.message,
            icon=icon_url or None,
            data={
                'action_url': action_url,
                'deep_link': getattr(notification, 'deep_link', '') or '',
            },
            actions=(
                [messaging.WebpushNotificationAction(action='open', title='Open')]
                if action_url else []
            ),
        )

        return messaging.WebpushConfig(
            headers={'TTL': '86400'},
            notification=webpush_notif,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_invalid_token_error(self, error_str: str) -> bool:
        error_lower = error_str.lower()
        return any(code in error_lower for code in self.INVALID_TOKEN_ERRORS)

    def _unavailable_response(self) -> Dict:
        return {
            'success': False,
            'provider': 'fcm',
            'message_id': '',
            'is_invalid_token': False,
            'error': 'FCMProvider not available — Firebase not initialised',
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
fcm_provider = FCMProvider()
