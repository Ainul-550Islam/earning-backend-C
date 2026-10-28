# api/support/signals_chat.py
"""Live chat specific signals."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='support.ChatSession')
def on_chat_session_saved(sender, instance, created, **kwargs):
    """When chat session created — track analytics."""
    if not created:
        return
    try:
        from api.support.integrations.project_specific.behavior_tracker import behavior_tracker
        behavior_tracker.track_chat_session(instance)
    except Exception as e:
        logger.debug(f'on_chat_session_saved: {e}')


@receiver(post_save, sender='support.ChatMessage')
def on_chat_message_created(sender, instance, created, **kwargs):
    """When chat message sent — analyze sentiment in real-time."""
    if not created or instance.is_agent or instance.is_bot:
        return
    try:
        from api.support.integrations.project_specific.ai_sentiment_realtime import sentiment_analyzer
        result = analyzer.analyze(instance.content, use_ai_engine=False)
        if result.get('frustration') == 'high':
            logger.info(
                f'High frustration in chat session {instance.session_id}'
            )
    except Exception as e:
        logger.debug(f'on_chat_message_created: {e}')