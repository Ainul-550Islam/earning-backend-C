# FILE 98 of 257 — notifications/InAppNotifier.py
# In-app notifications stored in DB + optionally sent via Django Channels websocket

from django.utils import timezone
import logging
logger = logging.getLogger(__name__)

class InAppNotifier:
    def send(self, user_id: int, notification_type: str, title: str, message: str, context: dict = None):
        try:
            from .models import InAppNotification
            notif = InAppNotification.objects.create(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                metadata=context or {},
            )
            self._push_realtime(user_id, notif)
            return notif
        except Exception as e:
            logger.error(f'InAppNotifier error: {e}')
            return None

    def _push_realtime(self, user_id: int, notif):
        """Push via Django Channels if available."""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f'user_{user_id}',
                    {'type': 'notification', 'data': {
                        'id': notif.id, 'title': notif.title,
                        'message': notif.message, 'type': notif.notification_type,
                    }}
                )
        except Exception:
            pass  # Channels not configured — that's OK

    def mark_read(self, user_id: int, notification_id: int):
        try:
            from .models import InAppNotification
            InAppNotification.objects.filter(id=notification_id, user_id=user_id).update(
                is_read=True, read_at=timezone.now()
            )
        except Exception as e:
            logger.error(f'InAppNotifier.mark_read error: {e}')

    def mark_all_read(self, user_id: int):
        try:
            from .models import InAppNotification
            InAppNotification.objects.filter(user_id=user_id, is_read=False).update(
                is_read=True, read_at=timezone.now()
            )
        except Exception as e:
            logger.error(f'InAppNotifier.mark_all_read error: {e}')
