# earning_backend/api/notifications/background_jobs.py
"""Background Jobs — High-level background job management for notifications."""
import logging
from typing import Dict, List, Optional
logger = logging.getLogger(__name__)

class NotificationJobManager:
    def schedule_send(self, notification_id, channel="in_app", priority="medium", delay_seconds=0):
        try:
            from api.notifications.tasks_cap import enqueue_notification_send
            return enqueue_notification_send(notification_id, channel, priority)
        except Exception as exc:
            logger.error(f"schedule_send: {exc}"); return None

    def schedule_campaign(self, campaign_id, send_at=None):
        try:
            from api.notifications.tasks.campaign_tasks import process_campaign_task
            kw = {"args":[campaign_id]}
            if send_at: kw["eta"] = send_at
            return process_campaign_task.apply_async(**kw).id
        except Exception as exc:
            logger.error(f"schedule_campaign: {exc}"); return None

    def schedule_batch(self, user_ids, notification_data, delay_seconds=0):
        try:
            from api.notifications.tasks.batch_send_tasks import process_batch_task
            return process_batch_task.apply_async(args=[user_ids,notification_data],countdown=delay_seconds).id
        except Exception as exc:
            logger.error(f"schedule_batch: {exc}"); return None

    def schedule_journey_step(self, user_id, journey_id, step_id, context, delay_seconds=0):
        try:
            from api.notifications.tasks.journey_tasks import execute_journey_step_task
            return execute_journey_step_task.apply_async(args=[user_id,journey_id,step_id,context],countdown=delay_seconds).id
        except Exception as exc:
            logger.error(f"schedule_journey_step: {exc}"); return None

    def cancel_job(self, task_id):
        from api.notifications.tasks_cap import revoke_task
        return revoke_task(task_id)

    def cancel_user_jobs(self, user_id):
        from api.notifications.tasks_cap import cancel_user_notification_tasks
        return cancel_user_notification_tasks(user_id)

    def get_job_status(self, task_id):
        try:
            from celery.result import AsyncResult
            r = AsyncResult(task_id)
            return {"task_id":task_id,"status":r.status,"ready":r.ready(),
                    "result":r.result if r.ready() and r.successful() else None,
                    "error":str(r.result) if r.ready() and not r.successful() else None}
        except Exception as exc:
            return {"task_id":task_id,"status":"unknown","error":str(exc)}

    def run_cleanup(self):
        try:
            from api.notifications.tasks.cleanup_tasks import run_all_cleanup
            return {"task_id":run_all_cleanup.apply_async().id,"queued":True}
        except Exception as exc:
            return {"error":str(exc),"queued":False}

job_manager = NotificationJobManager()
