# =============================================================================
# auto_mod/consumers.py
# =============================================================================

"""
WebSocket consumers for real-time auto moderation updates.
Provides live updates for queue status, decisions, appeals, and system metrics.
"""
from django.db.models import Avg

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import (
    ModerationQueue, ModerationDecision, ModerationAppeal, 
    SuspiciousSubmission, TaskBot, MLModelVersion
)
from .choices import ModerationStatus, AppealStatus, BotStatus
from .services import ModerationQueueService, AppealService

logger = logging.getLogger(__name__)
User = get_user_model()


class ModerationQueueConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time moderation queue updates.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        user = self.scope["user"]
        
        if not user.is_authenticated:
            await self.close()
            return
        
        if not (user.is_staff or user.groups.filter(name='moderators').exists()):
            await self.close()
            return
        
        self.user = user
        self.queue_group_name = "moderation_queue"
        
        # Join queue group
        await self.channel_layer.group_add(
            self.queue_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial queue status
        await self.send_queue_status()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.queue_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_queue_status':
                await self.send_queue_status()
            elif message_type == 'assign_item':
                await self.assign_queue_item(data)
            elif message_type == 'release_item':
                await self.release_queue_item(data)
            elif message_type == 'escalate_item':
                await self.escalate_queue_item(data)
            else:
                await self.send_error("Unknown message type")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as exc:
            logger.error(f"Queue consumer error: {exc}")
            await self.send_error("Internal error")
    
    async def send_queue_status(self):
        """Send current queue status to client."""
        try:
            queue_stats = await self.get_queue_stats()
            my_items = await self.get_my_queue_items()
            
            await self.send(text_data=json.dumps({
                'type': 'queue_status',
                'stats': queue_stats,
                'my_items': my_items,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as exc:
            logger.error(f"Error sending queue status: {exc}")
            await self.send_error("Failed to get queue status")
    
    async def assign_queue_item(self, data):
        """Assign queue item to current user."""
        try:
            queue_item_id = data.get('queue_item_id')
            if not queue_item_id:
                await self.send_error("queue_item_id required")
                return
            
            # Check if user can assign this item
            success = await self.can_assign_item(queue_item_id)
            if not success:
                await self.send_error("Cannot assign this item")
                return
            
            # Assign the item
            result = await self.assign_item_to_user(queue_item_id)
            
            await self.send(text_data=json.dumps({
                'type': 'item_assigned',
                'queue_item_id': queue_item_id,
                'result': result,
                'timestamp': timezone.now().isoformat()
            }))
            
            # Broadcast to all moderators
            await self.channel_layer.group_send(
                self.queue_group_name,
                {
                    'type': 'queue_update',
                    'message': {
                        'type': 'item_assigned',
                        'queue_item_id': queue_item_id,
                        'assigned_to': self.user.username,
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )
            
        except Exception as exc:
            logger.error(f"Error assigning queue item: {exc}")
            await self.send_error("Failed to assign item")
    
    async def release_queue_item(self, data):
        """Release queue item back to unassigned pool."""
        try:
            queue_item_id = data.get('queue_item_id')
            if not queue_item_id:
                await self.send_error("queue_item_id required")
                return
            
            # Release the item
            result = await self.release_item_from_user(queue_item_id)
            
            await self.send(text_data=json.dumps({
                'type': 'item_released',
                'queue_item_id': queue_item_id,
                'result': result,
                'timestamp': timezone.now().isoformat()
            }))
            
            # Broadcast to all moderators
            await self.channel_layer.group_send(
                self.queue_group_name,
                {
                    'type': 'queue_update',
                    'message': {
                        'type': 'item_released',
                        'queue_item_id': queue_item_id,
                        'released_by': self.user.username,
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )
            
        except Exception as exc:
            logger.error(f"Error releasing queue item: {exc}")
            await self.send_error("Failed to release item")
    
    async def escalate_queue_item(self, data):
        """Escalate queue item to higher priority."""
        try:
            queue_item_id = data.get('queue_item_id')
            new_priority = data.get('priority')
            reason = data.get('reason', 'Manual escalation')
            
            if not queue_item_id:
                await self.send_error("queue_item_id required")
                return
            
            # Escalate the item
            result = await self.escalate_item(queue_item_id, new_priority, reason)
            
            await self.send(text_data=json.dumps({
                'type': 'item_escalated',
                'queue_item_id': queue_item_id,
                'result': result,
                'timestamp': timezone.now().isoformat()
            }))
            
            # Broadcast to all moderators
            await self.channel_layer.group_send(
                self.queue_group_name,
                {
                    'type': 'queue_update',
                    'message': {
                        'type': 'item_escalated',
                        'queue_item_id': queue_item_id,
                        'escalated_by': self.user.username,
                        'new_priority': new_priority,
                        'reason': reason,
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )
            
        except Exception as exc:
            logger.error(f"Error escalating queue item: {exc}")
            await self.send_error("Failed to escalate item")
    
    async def queue_update(self, event):
        """Handle queue update broadcasts."""
        message = event['message']
        await self.send(text_data=json.dumps(message))
    
    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error_message,
            'timestamp': timezone.now().isoformat()
        }))
    
    @database_sync_to_async
    def get_queue_stats(self):
        """Get queue statistics."""
        service = ModerationQueueService()
        return service.get_queue_statistics()
    
    @database_sync_to_async
    def get_my_queue_items(self):
        """Get queue items assigned to current user."""
        service = ModerationQueueService()
        items = service.get_queue_items_for_moderator(
            moderator=self.user,
            limit=50,
            include_completed=False
        )
        
        return [
            {
                'id': str(item.pk),
                'submission_id': str(item.submission.pk),
                'content_id': item.submission.content_id,
                'priority': item.priority,
                'queued_at': item.queued_at.isoformat(),
                'due_at': item.due_at.isoformat(),
                'escalation_level': item.escalation_level,
                'is_overdue': item.is_overdue
            }
            for item in items
        ]
    
    @database_sync_to_async
    def can_assign_item(self, queue_item_id):
        """Check if user can assign this queue item."""
        try:
            item = ModerationQueue.objects.get(pk=queue_item_id)
            return item.assigned_to is None or item.assigned_to == self.user
        except ModerationQueue.DoesNotExist:
            return False
    
    @database_sync_to_async
    def assign_item_to_user(self, queue_item_id):
        """Assign queue item to user."""
        service = ModerationQueueService()
        item = ModerationQueue.objects.get(pk=queue_item_id)
        
        result = service.assign_to_moderator(
            queue_item=item,
            moderator=self.user,
            assigned_by=self.user
        )
        
        return {
            'success': True,
            'assigned_at': item.assigned_at.isoformat(),
            'assigned_by': self.user.username
        }
    
    @database_sync_to_async
    def release_item_from_user(self, queue_item_id):
        """Release queue item from user."""
        service = ModerationQueueService()
        item = ModerationQueue.objects.get(pk=queue_item_id)
        
        result = service.release_queue_item(
            queue_item=item,
            released_by=self.user,
            reason="Released via WebSocket"
        )
        
        return {
            'success': True,
            'released_at': timezone.now().isoformat(),
            'released_by': self.user.username
        }
    
    @database_sync_to_async
    def escalate_item(self, queue_item_id, new_priority, reason):
        """Escalate queue item."""
        service = ModerationQueueService()
        item = ModerationQueue.objects.get(pk=queue_item_id)
        
        result = service.escalate_queue_item(
            queue_item=item,
            new_priority=new_priority,
            reason=reason,
            escalated_by=self.user
        )
        
        return {
            'success': True,
            'escalated_at': timezone.now().isoformat(),
            'escalated_by': self.user.username,
            'new_priority': result.priority,
            'escalation_level': result.escalation_level
        }


class ModerationDecisionConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time moderation decision updates.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        user = self.scope["user"]
        
        if not user.is_authenticated:
            await self.close()
            return
        
        if not (user.is_staff or user.groups.filter(name__in=['moderators', 'reviewers']).exists()):
            await self.close()
            return
        
        self.user = user
        self.decision_group_name = "moderation_decisions"
        
        # Join decision group
        await self.channel_layer.group_add(
            self.decision_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial decision status
        await self.send_decision_status()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.decision_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_decision_status':
                await self.send_decision_status()
            elif message_type == 'get_recent_decisions':
                await self.send_recent_decisions(data)
            else:
                await self.send_error("Unknown message type")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as exc:
            logger.error(f"Decision consumer error: {exc}")
            await self.send_error("Internal error")
    
    async def send_decision_status(self):
        """Send current decision statistics."""
        try:
            stats = await self.get_decision_stats()
            
            await self.send(text_data=json.dumps({
                'type': 'decision_status',
                'stats': stats,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as exc:
            logger.error(f"Error sending decision status: {exc}")
            await self.send_error("Failed to get decision status")
    
    async def send_recent_decisions(self, data):
        """Send recent decisions."""
        try:
            limit = data.get('limit', 20)
            decisions = await self.get_recent_decisions(limit)
            
            await self.send(text_data=json.dumps({
                'type': 'recent_decisions',
                'decisions': decisions,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as exc:
            logger.error(f"Error sending recent decisions: {exc}")
            await self.send_error("Failed to get recent decisions")
    
    async def decision_update(self, event):
        """Handle decision update broadcasts."""
        message = event['message']
        await self.send(text_data=json.dumps(message))
    
    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error_message,
            'timestamp': timezone.now().isoformat()
        }))
    
    @database_sync_to_async
    def get_decision_stats(self):
        """Get decision statistics."""
        from django.db.models import Count, Q
        from datetime import timedelta
        
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        
        # Today's decisions
        today_decisions = ModerationDecision.objects.filter(decided_at__date=today)
        today_stats = today_decisions.aggregate(
            total=Count('id'),
            auto_approved=Count('id', filter=Q(decision_type='approve', is_automated=True)),
            auto_rejected=Count('id', filter=Q(decision_type='reject', is_automated=True)),
            human_approved=Count('id', filter=Q(decision_type='approve', is_automated=False)),
            human_rejected=Count('id', filter=Q(decision_type='reject', is_automated=False)),
        )
        
        # This week's decisions
        week_decisions = ModerationDecision.objects.filter(decided_at__gte=week_ago)
        week_stats = week_decisions.aggregate(
            total=Count('id'),
            avg_confidence=Avg('confidence'),
        )
        
        # Recent appeals
        recent_appeals = ModerationAppeal.objects.filter(
            created_at__gte=week_ago
        ).aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(final_decision='approve')),
            rejected=Count('id', filter=Q(final_decision='reject')),
        )
        
        return {
            'today': today_stats,
            'week': week_stats,
            'appeals': recent_appeals
        }
    
    @database_sync_to_async
    def get_recent_decisions(self, limit=20):
        """Get recent decisions."""
        decisions = ModerationDecision.objects.select_related(
            'submission', 'decided_by', 'applied_rule'
        ).order_by('-decided_at')[:limit]
        
        return [
            {
                'id': str(decision.pk),
                'submission_id': str(decision.submission.pk),
                'content_id': decision.submission.content_id,
                'decision_type': decision.decision_type,
                'confidence': decision.confidence,
                'is_automated': decision.is_automated,
                'decided_by': decision.decided_by.username if decision.decided_by else 'AI',
                'decided_at': decision.decided_at.isoformat(),
                'reason': decision.reason
            }
            for decision in decisions
        ]


class SystemMetricsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time system metrics and health status.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        user = self.scope["user"]
        
        if not user.is_authenticated:
            await self.close()
            return
        
        if not user.is_staff:
            await self.close()
            return
        
        self.user = user
        self.metrics_group_name = "system_metrics"
        
        # Join metrics group
        await self.channel_layer.group_add(
            self.metrics_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial metrics
        await self.send_system_metrics()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.metrics_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_metrics':
                await self.send_system_metrics()
            elif message_type == 'get_health':
                await self.send_health_status()
            elif message_type == 'get_bot_status':
                await self.send_bot_status()
            else:
                await self.send_error("Unknown message type")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as exc:
            logger.error(f"Metrics consumer error: {exc}")
            await self.send_error("Internal error")
    
    async def send_system_metrics(self):
        """Send current system metrics."""
        try:
            metrics = await self.get_system_metrics()
            
            await self.send(text_data=json.dumps({
                'type': 'system_metrics',
                'metrics': metrics,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as exc:
            logger.error(f"Error sending system metrics: {exc}")
            await self.send_error("Failed to get system metrics")
    
    async def send_health_status(self):
        """Send system health status."""
        try:
            health = await self.get_health_status()
            
            await self.send(text_data=json.dumps({
                'type': 'health_status',
                'health': health,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as exc:
            logger.error(f"Error sending health status: {exc}")
            await self.send_error("Failed to get health status")
    
    async def send_bot_status(self):
        """Send bot status."""
        try:
            bots = await self.get_bot_status()
            
            await self.send(text_data=json.dumps({
                'type': 'bot_status',
                'bots': bots,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as exc:
            logger.error(f"Error sending bot status: {exc}")
            await self.send_error("Failed to get bot status")
    
    async def metrics_update(self, event):
        """Handle metrics update broadcasts."""
        message = event['message']
        await self.send(text_data=json.dumps(message))
    
    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error_message,
            'timestamp': timezone.now().isoformat()
        }))
    
    @database_sync_to_async
    def get_system_metrics(self):
        """Get system metrics."""
        from django.db.models import Count, Avg, Q
        from datetime import timedelta
        
        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        # Queue metrics
        queue_metrics = ModerationQueue.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(assigned_to__isnull=True)),
            overdue=Count('id', filter=Q(due_at__lt=now)),
            high_priority=Count('id', filter=Q(priority__in=['high', 'urgent', 'critical']))
        )
        
        # Submission metrics
        submission_metrics = SuspiciousSubmission.objects.filter(
            created_at__gte=hour_ago
        ).aggregate(
            total=Count('id'),
            auto_approved=Count('id', filter=Q(status='auto_approved')),
            auto_rejected=Count('id', filter=Q(status='auto_rejected')),
            human_review=Count('id', filter=Q(status='human_review'))
        )
        
        # Decision metrics
        decision_metrics = ModerationDecision.objects.filter(
            decided_at__gte=hour_ago
        ).aggregate(
            total=Count('id'),
            avg_confidence=Avg('confidence'),
            automated=Count('id', filter=Q(is_automated=True))
        )
        
        # ML Model metrics
        model_metrics = MLModelVersion.objects.filter(
            is_active=True
        ).aggregate(
            total=Count('id'),
            avg_accuracy=Avg('accuracy')
        )
        
        return {
            'queue': queue_metrics,
            'submissions': submission_metrics,
            'decisions': decision_metrics,
            'models': model_metrics
        }
    
    @database_sync_to_async
    def get_health_status(self):
        """Get system health status."""
        # Check queue health
        queue_overdue = ModerationQueue.objects.filter(
            due_at__lt=timezone.now()
        ).count()
        
        # Check bot health
        healthy_bots = TaskBot.objects.filter(
            status=BotStatus.RUNNING
        ).count()
        total_bots = TaskBot.objects.count()
        
        # Check model health
        active_models = MLModelVersion.objects.filter(
            is_active=True,
            status='deployed'
        ).count()
        
        # Overall health score
        health_score = 100
        if queue_overdue > 0:
            health_score -= min(queue_overdue * 5, 30)
        if total_bots > 0 and healthy_bots < total_bots:
            health_score -= ((total_bots - healthy_bots) * 10)
        if active_models == 0:
            health_score -= 20
        
        health_score = max(0, health_score)
        
        return {
            'overall_score': health_score,
            'status': 'healthy' if health_score >= 80 else 'warning' if health_score >= 60 else 'critical',
            'queue_overdue': queue_overdue,
            'healthy_bots': healthy_bots,
            'total_bots': total_bots,
            'active_models': active_models
        }
    
    @database_sync_to_async
    def get_bot_status(self):
        """Get bot status."""
        bots = TaskBot.objects.all().order_by('name')
        
        return [
            {
                'id': str(bot.pk),
                'name': bot.name,
                'status': bot.status,
                'submission_type': bot.submission_type,
                'total_processed': bot.total_processed,
                'approval_rate': bot.approval_rate,
                'is_healthy': bot.is_healthy,
                'last_heartbeat': bot.last_heartbeat.isoformat() if bot.last_heartbeat else None,
                'last_error': bot.last_error
            }
            for bot in bots
        ]


# Utility functions for broadcasting updates
def broadcast_queue_update(message_type, data):
    """Broadcast queue update to all connected moderators."""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        "moderation_queue",
        {
            'type': 'queue_update',
            'message': {
                'type': message_type,
                'data': data,
                'timestamp': timezone.now().isoformat()
            }
        }
    )


def broadcast_decision_update(message_type, data):
    """Broadcast decision update to all connected reviewers."""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        "moderation_decisions",
        {
            'type': 'decision_update',
            'message': {
                'type': message_type,
                'data': data,
                'timestamp': timezone.now().isoformat()
            }
        }
    )


def broadcast_metrics_update(message_type, data):
    """Broadcast metrics update to all connected staff."""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        "system_metrics",
        {
            'type': 'metrics_update',
            'message': {
                'type': message_type,
                'data': data,
                'timestamp': timezone.now().isoformat()
            }
        }
    )


# Signal handlers to trigger WebSocket broadcasts
def queue_item_assigned_handler(sender, instance, assigned_to, **kwargs):
    """Handle queue item assignment broadcast."""
    broadcast_queue_update('item_assigned', {
        'queue_item_id': str(instance.pk),
        'assigned_to': assigned_to.username if assigned_to else None,
        'submission_id': str(instance.submission.pk)
    })


def decision_made_handler(sender, instance, **kwargs):
    """Handle decision broadcast."""
    broadcast_decision_update('decision_made', {
        'decision_id': str(instance.pk),
        'submission_id': str(instance.submission.pk),
        'decision_type': instance.decision_type,
        'is_automated': instance.is_automated
    })


def system_health_update_handler(sender, health_data, **kwargs):
    """Handle system health broadcast."""
    broadcast_metrics_update('health_update', health_data)
