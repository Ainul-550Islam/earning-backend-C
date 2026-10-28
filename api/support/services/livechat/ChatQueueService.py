# api/support/services/livechat/ChatQueueService.py  — WORLD #1
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)

class ChatQueueService:
    def join(self, user, department=None):
        from api.support.models import ChatQueue
        # Get current queue length
        position = ChatQueue.objects.filter(is_active=True).count() + 1
        entry = ChatQueue.objects.create(
            user=user, department=department,
            position=position, estimated_wait_minutes=position * 3,
        )
        return {'position': position, 'estimated_wait_minutes': entry.estimated_wait_minutes, 'queue_id': entry.id}

    def leave(self, user_id: int) -> bool:
        from api.support.models import ChatQueue
        updated = ChatQueue.objects.filter(user_id=user_id, is_active=True).update(is_active=False)
        return updated > 0

    def get_position(self, user_id: int) -> dict:
        from api.support.models import ChatQueue
        try:
            entry = ChatQueue.objects.get(user_id=user_id, is_active=True)
            return {'position': entry.position, 'estimated_wait_minutes': entry.estimated_wait_minutes}
        except ChatQueue.DoesNotExist:
            return {'position': 0, 'in_queue': False}

    def rebalance(self):
        from api.support.models import ChatQueue
        entries = ChatQueue.objects.filter(is_active=True).order_by('joined_at')
        for i, entry in enumerate(entries, 1):
            entry.position = i
            entry.estimated_wait_minutes = i * 3
        ChatQueue.objects.bulk_update(entries, ['position','estimated_wait_minutes'])

chat_queue_service = ChatQueueService()