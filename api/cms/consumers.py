# api/cms/consumers.py
"""
Django Channels WebSocket consumers for real-time CMS features.
Real-time: notifications, leaderboard updates, earning alerts, offer feed.
"""
from django.db import models
from django.utils import timezone
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CMSNotificationConsumer(AsyncWebsocketConsumer):
    """
    Real-time notification consumer.
    URL: ws://site.com/ws/cms/notifications/
    Sends: reward_earned, offer_completed, streak_milestone, withdrawal_update
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"cms_notifications_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug(f"[WS] Notification connected: user={self.user.id}")

        # Send unread count on connect
        count = await self._get_unread_count()
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "unread_count": count,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type", "")
            if msg_type == "mark_read":
                await self._mark_notifications_read()
                await self.send(text_data=json.dumps({"type": "marked_read"}))
        except Exception as e:
            logger.error(f"[WS] Notification receive error: {e}")
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    @database_sync_to_async
    def _get_unread_count(self):
        from api.cms.models_new.notifications import Notification
        return Notification.objects.filter(user=self.user, read=False).count()

    @database_sync_to_async
    def _mark_notifications_read(self):
        from api.cms.models_new.notifications import Notification
        Notification.objects.filter(user=self.user, read=False).update(read=True)


class SurveyConsumer(AsyncWebsocketConsumer):
    """
    Real-time survey updates consumer.
    URL: ws://site.com/ws/cms/surveys/
    Sends: new_surveys, survey_completed, survey_expired, quality_updates
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"cms_surveys_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug(f"[WS] Survey connected: user={self.user.id}")

        # Send available surveys on connect
        await self._send_available_surveys()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type", "")
            
            if msg_type == "start_survey":
                await self._handle_survey_start(data)
            elif msg_type == "submit_response":
                await self._handle_survey_submit(data)
            elif msg_type == "get_recommendations":
                await self._send_survey_recommendations()
        except Exception as e:
            logger.error(f"[WS] Survey receive error: {e}")
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    @database_sync_to_async
    def _send_available_surveys(self):
        from api.cms.services_new.ProfileSurveyService import ProfileSurveyManager
        manager = ProfileSurveyManager()
        surveys = manager.get_available_surveys(self.user)
        
        survey_data = [{
            "uuid": str(survey.uuid),
            "title": survey.title,
            "description": survey.description,
            "estimated_time": survey.estimated_completion_time,
            "reward_amount": float(survey.min_reward) if survey.min_reward else 0,
        } for survey in surveys[:10]]  # Limit to 10 surveys
        
        return survey_data

    @database_sync_to_async
    def _send_survey_recommendations(self):
        from api.cms.services_new.ProfileSurveyService import ProfileSurveyManager
        manager = ProfileSurveyManager()
        recommendations = manager.get_survey_recommendations(self.user)
        
        return [{"uuid": str(rec.uuid), "title": rec.title} for rec in recommendations[:5]]

    @database_sync_to_async
    def _handle_survey_start(self, data):
        survey_uuid = data.get("survey_uuid")
        if not survey_uuid:
            return
        
        from api.cms.services_new.ProfileSurveyService import ProfileSurveyManager
        manager = ProfileSurveyManager()
        return manager.start_survey(self.user, survey_uuid)

    @database_sync_to_async
    def _handle_survey_submit(self, data):
        survey_uuid = data.get("survey_uuid")
        responses = data.get("responses", [])
        if not survey_uuid or not responses:
            return
        
        from api.cms.services_new.ProfileSurveyService import ProfileSurveyManager
        manager = ProfileSurveyManager()
        return manager.submit_survey(self.user, survey_uuid, responses)


class RewardConsumer(AsyncWebsocketConsumer):
    """
    Real-time reward updates consumer.
    URL: ws://site.com/ws/cms/rewards/
    Sends: reward_earned, reward_approved, reward_paid, pool_updates
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"cms_rewards_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug(f"[WS] Reward connected: user={self.user.id}")

        # Send reward summary on connect
        await self._send_reward_summary()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type", "")
            
            if msg_type == "get_transactions":
                await self._send_transaction_history(data.get("limit", 20))
            elif msg_type == "get_pool_status":
                await self._send_pool_status()
        except Exception as e:
            logger.error(f"[WS] Reward receive error: {e}")
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    @database_sync_to_async
    def _send_reward_summary(self):
        from api.cms.services_new.SurveyRewardService import SurveyRewardService
        service = SurveyRewardService()
        summary = service.get_user_reward_summary(self.user.id, 30)
        
        return {
            "total_transactions": summary.get("total_transactions", 0),
            "total_amount": float(summary.get("total_amount", 0)),
            "pending_amount": float(summary.get("pending_amount", 0)),
            "approved_amount": float(summary.get("approved_amount", 0)),
        }

    @database_sync_to_async
    def _send_transaction_history(self, limit):
        from api.cms.models_new.survey_rewards import RewardTransaction
        transactions = RewardTransaction.objects.filter(
            user=self.user
        ).order_by('-created_at')[:limit]
        
        return [{
            "uuid": str(tx.uuid),
            "amount": float(tx.amount),
            "type": tx.transaction_type,
            "status": tx.status,
            "description": tx.description,
            "created_at": tx.created_at.isoformat(),
        } for tx in transactions]

    @database_sync_to_async
    def _send_pool_status(self):
        from api.cms.models_new.survey_rewards import RewardPool
        pools = RewardPool.objects.filter(is_active=True)
        
        return [{
            "uuid": str(pool.uuid),
            "name": pool.name,
            "total_budget": float(pool.total_budget),
            "allocated_amount": float(pool.allocated_amount),
            "paid_amount": float(pool.paid_amount),
            "utilization_rate": (pool.allocated_amount / pool.total_budget * 100) if pool.total_budget > 0 else 0,
        } for pool in pools]


class TaskConsumer(AsyncWebsocketConsumer):
    """
    Real-time task management consumer.
    URL: ws://site.com/ws/cms/tasks/
    Sends: task_started, task_completed, task_failed, queue_updates
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Check if user is admin/staff for task monitoring
        if not (self.user.is_staff or self.user.is_superuser):
            await self.close(code=4003)
            return

        self.group_name = "cms_tasks_admin"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug(f"[WS] Task connected: user={self.user.id}")

        # Send task status overview on connect
        await self._send_task_overview()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type", "")
            
            if msg_type == "get_task_status":
                await self._send_task_status(data.get("task_uuid"))
            elif msg_type == "get_queue_status":
                await self._send_queue_status()
            elif msg_type == "trigger_task":
                await self._trigger_task(data.get("task_uuid"))
        except Exception as e:
            logger.error(f"[WS] Task receive error: {e}")
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    @database_sync_to_async
    def _send_task_overview(self):
        from api.cms.services_new.TaskManagementService import TaskManagementService
        service = TaskManagementService()
        stats = service.get_task_statistics()
        
        return {
            "total_schedules": stats.get("total_schedules", 0),
            "active_schedules": stats.get("active_schedules", 0),
            "running_tasks": stats.get("running_tasks", 0),
            "failed_tasks_today": stats.get("failed_tasks_today", 0),
            "success_rate": stats.get("success_rate", 0),
        }

    @database_sync_to_async
    def _send_task_status(self, task_uuid):
        from api.cms.models_new.task_management import TaskExecution
        try:
            execution = TaskExecution.objects.filter(schedule__uuid=task_uuid).latest('started_at')
            return {
                "uuid": str(execution.uuid),
                "status": execution.status,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "runtime_seconds": execution.runtime_seconds,
                "error_message": execution.error_message,
            }
        except TaskExecution.DoesNotExist:
            return {"error": "Task execution not found"}

    @database_sync_to_async
    def _send_queue_status(self):
        from api.cms.models_new.task_management import TaskQueue
        queue_stats = TaskQueue.objects.values('status').annotate(count=models.Count('id'))
        
        return {
            "total_queued": TaskQueue.objects.filter(status='queued').count(),
            "processing": TaskQueue.objects.filter(status='processing').count(),
            "failed_today": TaskQueue.objects.filter(
                status='failed',
                created_at__date=timezone.now().date()
            ).count(),
        }

    @database_sync_to_async
    def _trigger_task(self, task_uuid):
        from api.cms.services_new.TaskManagementService import TaskManagementService
        service = TaskManagementService()
        return service.execute_task(task_uuid)
    """
    Real-time notification consumer.
    URL: ws://site.com/ws/cms/notifications/
    Sends: reward_earned, offer_completed, streak_milestone, withdrawal_update
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"cms_notifications_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug(f"[WS] Notification connected: user={self.user.id}")

        # Send unread count on connect
        count = await self._get_unread_count()
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "unread_count": count,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type", "")
            if msg_type == "mark_read":
                await self._mark_notifications_read()
                await self.send(text_data=json.dumps({"type": "marked_read"}))
            elif msg_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except Exception as e:
            logger.warning(f"[WS] receive error: {e}")

    # ── Group message handlers ───────────────────────────────────

    async def cms_notification(self, event):
        """Receive notification from group and forward to WebSocket."""
        await self.send(text_data=json.dumps({
            "type": "notification",
            "notification": event.get("notification", {}),
        }))

    async def cms_reward(self, event):
        """Real-time reward alert."""
        await self.send(text_data=json.dumps({
            "type": "reward_earned",
            "amount": event.get("amount", 0),
            "currency": event.get("currency", "Coins"),
            "source": event.get("source", ""),
            "new_balance": event.get("new_balance", 0),
        }))

    async def cms_leaderboard_update(self, event):
        """Leaderboard rank change."""
        await self.send(text_data=json.dumps({
            "type": "leaderboard_update",
            "rank": event.get("rank", 0),
            "score": event.get("score", 0),
        }))

    # ── DB helpers ───────────────────────────────────────────────

    @database_sync_to_async
    def _get_unread_count(self):
        try:
            from api.cms.models_new.extras import Notification
            return Notification.objects.filter(user=self.user, is_read=False).count()
        except Exception:
            return 0

    @database_sync_to_async
    def _mark_notifications_read(self):
        try:
            from api.cms.models_new.extras import Notification
            Notification.objects.filter(user=self.user, is_read=False).update(is_read=True)
        except Exception:
            pass


class CMSOfferFeedConsumer(AsyncWebsocketConsumer):
    """
    Real-time offer feed consumer.
    URL: ws://site.com/ws/cms/offers/
    Streams: new offers, offer updates, featured offer alerts.
    """

    async def connect(self):
        self.group_name = "cms_offer_feed"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send current offers on connect
        offers = await self._get_current_offers()
        await self.send(text_data=json.dumps({
            "type": "offer_list",
            "offers": offers,
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get("type") == "refresh":
                offers = await self._get_current_offers(force_refresh=True)
                await self.send(text_data=json.dumps({
                    "type": "offer_list",
                    "offers": offers,
                }))
        except Exception as e:
            logger.warning(f"[WS] offer feed receive error: {e}")

    async def cms_new_offer(self, event):
        """Broadcast new offer to all connected clients."""
        await self.send(text_data=json.dumps({
            "type": "new_offer",
            "offer": event.get("offer", {}),
        }))

    @database_sync_to_async
    def _get_current_offers(self, force_refresh=False):
        try:
            if not force_refresh:
                cached = cache.get("ws_offers_cache")
                if cached:
                    return cached
            from api.cms.services_new.CPALeadService import CPALeadService
            offers = CPALeadService._get_cached_offers(limit=20)
            data = [{
                "offer_id": o.offer_id, "title": o.title,
                "payout_coins": float(o.payout_virtual),
                "payout_usd": float(o.payout_usd),
                "offer_type": o.offer_type, "is_featured": o.is_featured,
                "icon_url": o.icon_url, "is_quiz": o.is_quiz,
            } for o in offers]
            cache.set("ws_offers_cache", data, 300)
            return data
        except Exception:
            return []


class CMSLeaderboardConsumer(AsyncWebsocketConsumer):
    """
    Real-time leaderboard consumer.
    URL: ws://site.com/ws/cms/leaderboard/
    Sends: rank updates every minute.
    """

    async def connect(self):
        self.group_name = "cms_leaderboard"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        top = await self._get_top()
        await self.send(text_data=json.dumps({"type": "leaderboard", "data": top}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def cms_leaderboard_refresh(self, event):
        top = await self._get_top()
        await self.send(text_data=json.dumps({"type": "leaderboard", "data": top}))

    @database_sync_to_async
    def _get_top(self):
        try:
            from api.cms.services_new.LeaderboardService import LeaderboardService
            return LeaderboardService.get_top(period_type='weekly', limit=10)
        except Exception:
            return []
