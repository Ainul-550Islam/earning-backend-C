# api/djoyalty/integrations/fcm.py
"""
FCMPushIntegration -- Firebase Cloud Messaging push notification adapter.
World reference: Firebase Admin SDK for Python.
Used by NotificationService._send_push() for mobile push delivery.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FCMPushIntegration:
    """
    Firebase Cloud Messaging push adapter.
    Requires FIREBASE_CREDENTIALS in Django settings (path to serviceAccountKey.json).
    Falls back gracefully if firebase_admin is not installed.
    """

    _app = None  # firebase_admin App singleton

    @classmethod
    def _get_app(cls):
        """Lazy-initialize Firebase Admin app."""
        if cls._app is not None:
            return cls._app
        try:
            import firebase_admin
            from firebase_admin import credentials
            from django.conf import settings
            cred_path = getattr(settings, 'FIREBASE_CREDENTIALS', None)
            if not cred_path:
                logger.warning('FCMPushIntegration: FIREBASE_CREDENTIALS not set in settings')
                return None
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                cls._app = firebase_admin.initialize_app(cred)
            else:
                cls._app = firebase_admin.get_app()
            return cls._app
        except ImportError:
            logger.warning('FCMPushIntegration: firebase_admin not installed. pip install firebase-admin')
            return None
        except Exception as e:
            logger.error('FCMPushIntegration._get_app error: %s', e)
            return None

    @classmethod
    def send(cls, token: str, title: str, body: str,
             data: dict = None, image_url: str = '') -> dict:
        """
        Send push notification to a single FCM token.
        Returns: {'success': True, 'message_id': str} or {'success': False, 'error': str}
        """
        try:
            app = cls._get_app()
            if not app:
                return {'success': False, 'error': 'FCM not configured'}

            from firebase_admin import messaging
            msg = messaging.Message(
                token=token,
                notification=messaging.Notification(
                    title=title,
                    body=body,
                    image=image_url or None,
                ),
                data={str(k): str(v) for k, v in (data or {}).items()},
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        click_action='FLUTTER_NOTIFICATION_CLICK',
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound='default', badge=1),
                    ),
                ),
            )
            response = messaging.send(msg)
            logger.info('FCMPushIntegration.send: message_id=%s', response)
            return {'success': True, 'message_id': response}
        except Exception as e:
            logger.error('FCMPushIntegration.send error token=%s: %s', token[:20], e)
            return {'success': False, 'error': str(e)}

    @classmethod
    def send_multicast(cls, tokens: list, title: str, body: str,
                        data: dict = None) -> dict:
        """
        Send to multiple FCM tokens (up to 500 per call).
        Returns: {'success_count': N, 'failure_count': N, 'responses': [...]}
        """
        try:
            if not tokens:
                return {'success_count': 0, 'failure_count': 0, 'responses': []}
            app = cls._get_app()
            if not app:
                return {'success_count': 0, 'failure_count': len(tokens),
                        'error': 'FCM not configured'}

            from firebase_admin import messaging
            msg = messaging.MulticastMessage(
                tokens=tokens[:500],
                notification=messaging.Notification(title=title, body=body),
                data={str(k): str(v) for k, v in (data or {}).items()},
                android=messaging.AndroidConfig(priority='high'),
            )
            response = messaging.send_each_for_multicast(msg)
            return {
                'success_count': response.success_count,
                'failure_count': response.failure_count,
                'responses': [
                    {'success': r.success, 'message_id': r.message_id, 'error': str(r.exception) if r.exception else None}
                    for r in response.responses
                ],
            }
        except Exception as e:
            logger.error('FCMPushIntegration.send_multicast error: %s', e)
            return {'success_count': 0, 'failure_count': len(tokens), 'error': str(e)}

    @classmethod
    def validate_token(cls, token: str) -> bool:
        """Quick check if token looks valid (format check only)."""
        return bool(token and len(token) > 20 and ':' in token)
