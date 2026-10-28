# engagement/services/notification_service.py
import logging
from django.utils import timezone
from ..models.notification import Notification, UserPushToken

logger = logging.getLogger(__name__)


class NotificationService:

    @classmethod
    def send(cls, user, notif_type: str, title: str, body: str = "",
             data: dict = None, icon: str = "", tenant=None) -> Notification:
        """Create an in-app notification and optionally fire a push."""
        notif = Notification.objects.create(
            user   = user,
            tenant = tenant or getattr(user, "tenant", None),
            type   = notif_type,
            title  = title,
            body   = body,
            icon   = icon,
            data   = data or {},
        )
        cls._send_push(user, title, body, data or {}, notif)
        return notif

    @classmethod
    def bulk_send(cls, users, notif_type: str, title: str, body: str = "",
                  data: dict = None, tenant=None):
        """Create notifications for multiple users in bulk (no push, use celery task)."""
        rows = [
            Notification(
                user   = u,
                tenant = tenant or getattr(u, "tenant", None),
                type   = notif_type,
                title  = title,
                body   = body,
                data   = data or {},
            )
            for u in users
        ]
        Notification.objects.bulk_create(rows, ignore_conflicts=True)

    @staticmethod
    def mark_read(user, notification_id: int):
        try:
            n = Notification.objects.get(pk=notification_id, user=user)
            n.mark_read()
        except Notification.DoesNotExist:
            pass

    @staticmethod
    def mark_all_read(user):
        Notification.objects.filter(user=user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )

    @staticmethod
    def unread_count(user) -> int:
        return Notification.objects.filter(user=user, is_read=False).count()

    # ── Private ───────────────────────────────────────────────────────────────

    @classmethod
    def _send_push(cls, user, title: str, body: str, data: dict, notif: Notification):
        tokens = UserPushToken.objects.filter(user=user, is_active=True)
        if not tokens.exists():
            return
        try:
            from .push_fcm import FCMService
            for token in tokens:
                if token.platform == "fcm":
                    FCMService.send(token.token, title, body, data)
            notif.push_sent    = True
            notif.push_sent_at = timezone.now()
            notif.save(update_fields=["push_sent", "push_sent_at"])
        except Exception as exc:
            logger.warning("Push send failed for user=%s: %s", user.pk, exc)
