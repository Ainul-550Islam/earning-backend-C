# api/support/signals/chat_signals.py  — WORLD #1
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
logger = logging.getLogger(__name__)

@receiver(post_save, sender='support.ChatSession')
def on_chat_session_save(sender, instance, created, **kwargs):
    if created:
        # Notify available agent
        try:
            from api.support.notifications.notification_router import notification_router
            notification_router.notify_new_chat(instance)
        except Exception as e:
            logger.debug(f"Chat session notify failed: {e}")
    elif instance.status == "ended" and not created:
        # Generate transcript
        try:
            from api.support.tasks.chat_tasks import generate_chat_transcript
            generate_chat_transcript.apply_async(args=[str(instance.session_id)])
        except Exception:
            pass