# engagement/services/push_fcm.py
"""
Firebase Cloud Messaging (FCM) push notification sender.
Requires:  pip install firebase-admin
Settings:  FIREBASE_CREDENTIALS_PATH = "/path/to/serviceAccount.json"
           OR
           FIREBASE_CREDENTIALS_DICT = { ... }  (dict from env)
"""
import logging
import json
from django.conf import settings

logger = logging.getLogger(__name__)

_fcm_app = None  # lazy singleton


def _get_app():
    """Initialise firebase_admin once and cache the app object."""
    global _fcm_app
    if _fcm_app is not None:
        return _fcm_app

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Option 1 — JSON file path in settings
        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", None)
        cred_dict = getattr(settings, "FIREBASE_CREDENTIALS_DICT", None)

        if cred_path:
            cred = credentials.Certificate(cred_path)
        elif cred_dict:
            if isinstance(cred_dict, str):
                cred_dict = json.loads(cred_dict)
            cred = credentials.Certificate(cred_dict)
        else:
            logger.warning("FCMService: No Firebase credentials configured. Push disabled.")
            return None

        _fcm_app = firebase_admin.initialize_app(cred)
        logger.info("FCMService: Firebase app initialised.")
    except ImportError:
        logger.warning("FCMService: firebase-admin not installed. Run: pip install firebase-admin")
        _fcm_app = None
    except Exception as exc:
        logger.error("FCMService: init failed — %s", exc)
        _fcm_app = None

    return _fcm_app


class FCMService:
    """
    Thin wrapper around firebase_admin messaging.
    All methods fail silently with a log warning if Firebase is not configured.
    """

    @classmethod
    def send(cls, token: str, title: str, body: str, data: dict = None) -> bool:
        """
        Send a push notification to a single FCM token.
        Returns True on success, False on failure.
        """
        app = _get_app()
        if app is None:
            return False

        try:
            from firebase_admin import messaging

            # FCM data payload values must be strings
            str_data = {k: str(v) for k, v in (data or {}).items()}

            message = messaging.Message(
                token=token,
                notification=messaging.Notification(title=title, body=body),
                data=str_data,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        title=title,
                        body=body,
                        sound="default",
                        click_action="FLUTTER_NOTIFICATION_CLICK",
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(title=title, body=body),
                            sound="default",
                            badge=1,
                        )
                    )
                ),
            )
            response = messaging.send(message, app=app)
            logger.debug("FCMService.send: success message_id=%s", response)
            return True

        except Exception as exc:
            logger.warning("FCMService.send failed token=%s…: %s", token[:12], exc)
            return False

    @classmethod
    def send_multicast(cls, tokens: list, title: str, body: str, data: dict = None) -> dict:
        """
        Send push to multiple FCM tokens at once (max 500 per call).
        Returns {"success": N, "failure": M}.
        """
        app = _get_app()
        if app is None:
            return {"success": 0, "failure": len(tokens)}

        if not tokens:
            return {"success": 0, "failure": 0}

        try:
            from firebase_admin import messaging

            str_data = {k: str(v) for k, v in (data or {}).items()}

            # FCM multicast limit is 500 tokens per request
            success_total = 0
            failure_total = 0

            for i in range(0, len(tokens), 500):
                chunk = tokens[i : i + 500]
                multicast_message = messaging.MulticastMessage(
                    tokens=chunk,
                    notification=messaging.Notification(title=title, body=body),
                    data=str_data,
                )
                response = messaging.send_each_for_multicast(multicast_message, app=app)
                success_total += response.success_count
                failure_total += response.failure_count

                # Deactivate tokens that are no longer valid
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        cls._handle_invalid_token(chunk[idx], resp.exception)

            logger.info(
                "FCMService.send_multicast: success=%d failure=%d tokens=%d",
                success_total, failure_total, len(tokens),
            )
            return {"success": success_total, "failure": failure_total}

        except Exception as exc:
            logger.error("FCMService.send_multicast failed: %s", exc)
            return {"success": 0, "failure": len(tokens)}

    @staticmethod
    def _handle_invalid_token(token: str, exception):
        """
        If Firebase reports a token as invalid/unregistered, deactivate it in DB.
        """
        try:
            from firebase_admin.exceptions import InvalidArgumentError, NotFoundError
            from firebase_admin.messaging import UnregisteredError

            if isinstance(exception, (UnregisteredError, NotFoundError)):
                from ..models.notification import UserPushToken
                updated = UserPushToken.objects.filter(token=token).update(is_active=False)
                if updated:
                    logger.info("FCMService: deactivated invalid token %s…", token[:12])
        except Exception as inner_exc:
            logger.debug("FCMService._handle_invalid_token: %s", inner_exc)
