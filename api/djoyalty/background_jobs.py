# api/djoyalty/background_jobs.py
"""
Djoyalty Background Jobs -- High-level background job orchestrator।
Wraps Celery tasks with retry, monitoring, and error handling।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class LoyaltyJobRunner:
    """
    High-level background job runner।
    Abstracts Celery task dispatch with error handling and monitoring।

    Usage:
        jobs = LoyaltyJobRunner()
        jobs.run_earn_for_customer(customer_id=1, amount=500)
        jobs.run_tier_evaluation(customer_id=1)
        jobs.schedule_expiry_warnings()
    """

    @staticmethod
    def _dispatch(task_fn, *args, queue: str = 'djoyalty_bulk',
                   countdown: int = 0, **kwargs) -> Optional[str]:
        """Dispatch a Celery task with error handling।"""
        try:
            if countdown:
                result = task_fn.apply_async(
                    args=args, kwargs=kwargs,
                    queue=queue, countdown=countdown,
                )
            else:
                result = task_fn.apply_async(
                    args=args, kwargs=kwargs, queue=queue,
                )
            return result.id if result else None
        except Exception as e:
            logger.error('LoyaltyJobRunner._dispatch [%s] error: %s',
                         task_fn.name if hasattr(task_fn, 'name') else str(task_fn), e)
            return None

    # ─── Points Jobs ─────────────────────────────────────────────

    @staticmethod
    def run_expire_points():
        """Run daily points expiry job."""
        try:
            from .tasks.points_expiry_tasks import expire_points_task
            return LoyaltyJobRunner._dispatch(
                expire_points_task, queue='djoyalty_points'
            )
        except Exception as e:
            logger.error('run_expire_points error: %s', e)

    @staticmethod
    def run_send_expiry_warnings(days_before: int = 7):
        """Send expiry warning notifications."""
        try:
            from .tasks.notification_delivery_tasks import send_expiry_warnings_task
            return LoyaltyJobRunner._dispatch(
                send_expiry_warnings_task,
                kwargs={'days_before': days_before},
                queue='djoyalty_notifications',
            )
        except Exception as e:
            logger.error('run_send_expiry_warnings error: %s', e)

    # ─── Tier Jobs ───────────────────────────────────────────────

    @staticmethod
    def run_evaluate_all_tiers():
        """Run monthly tier evaluation for all customers."""
        try:
            from .tasks.tier_evaluation_tasks import evaluate_all_tiers_task
            return LoyaltyJobRunner._dispatch(
                evaluate_all_tiers_task, queue='djoyalty_bulk'
            )
        except Exception as e:
            logger.error('run_evaluate_all_tiers error: %s', e)

    # ─── AI Jobs ─────────────────────────────────────────────────

    @staticmethod
    def run_compute_rfm():
        """Compute RFM scores for all customers."""
        try:
            from .tasks.ai_personalization_tasks import compute_rfm_scores_task
            return LoyaltyJobRunner._dispatch(
                compute_rfm_scores_task, queue='djoyalty_ai'
            )
        except Exception as e:
            logger.error('run_compute_rfm error: %s', e)

    @staticmethod
    def run_churn_scan():
        """Run churn scan and generate win-back offers."""
        try:
            from .tasks.ai_personalization_tasks import run_churn_scan_task
            return LoyaltyJobRunner._dispatch(
                run_churn_scan_task, queue='djoyalty_ai'
            )
        except Exception as e:
            logger.error('run_churn_scan error: %s', e)

    # ─── Notification Jobs ───────────────────────────────────────

    @staticmethod
    def run_cleanup_old_notifications(days: int = 90):
        """Clean up old notifications."""
        try:
            from .tasks.notification_delivery_tasks import cleanup_old_notifications_task
            return LoyaltyJobRunner._dispatch(
                cleanup_old_notifications_task,
                kwargs={'days': days},
                queue='djoyalty_bulk',
            )
        except Exception as e:
            logger.error('run_cleanup_old_notifications error: %s', e)

    # ─── OfferWall Jobs ──────────────────────────────────────────

    @staticmethod
    def run_sync_cpalead_offers(wall_id: int):
        """Sync offers from CPAlead API."""
        try:
            from .tasks.offerwall_sync_tasks import sync_cpalead_offers_task
            return LoyaltyJobRunner._dispatch(
                sync_cpalead_offers_task,
                kwargs={'offer_wall_id': wall_id},
                queue='djoyalty_bulk',
            )
        except Exception as e:
            logger.error('run_sync_cpalead_offers error: %s', e)

    @staticmethod
    def run_retry_postbacks():
        """Retry failed postbacks."""
        try:
            from .tasks.offerwall_sync_tasks import retry_pending_postbacks_task
            return LoyaltyJobRunner._dispatch(
                retry_pending_postbacks_task, queue='djoyalty_webhooks'
            )
        except Exception as e:
            logger.error('run_retry_postbacks error: %s', e)

    # ─── Process Receipt ─────────────────────────────────────────

    @staticmethod
    def run_process_receipt(scan_id: int):
        """Process a receipt scan via OCR."""
        try:
            from .tasks.receipt_scan_tasks import process_receipt_scan_task
            return LoyaltyJobRunner._dispatch(
                process_receipt_scan_task,
                kwargs={'scan_id': scan_id},
                queue='djoyalty_ai',
            )
        except Exception as e:
            logger.error('run_process_receipt error: %s', e)

    # ─── All Daily Jobs ──────────────────────────────────────────

    @staticmethod
    def run_all_daily_jobs():
        """Run all daily maintenance jobs -- for testing/manual trigger।"""
        results = {}
        jobs = [
            ('expire_points', LoyaltyJobRunner.run_expire_points),
            ('expiry_warnings_7d', lambda: LoyaltyJobRunner.run_send_expiry_warnings(7)),
            ('expiry_warnings_3d', lambda: LoyaltyJobRunner.run_send_expiry_warnings(3)),
            ('compute_rfm', LoyaltyJobRunner.run_compute_rfm),
            ('churn_scan', LoyaltyJobRunner.run_churn_scan),
            ('retry_postbacks', LoyaltyJobRunner.run_retry_postbacks),
        ]
        for name, fn in jobs:
            try:
                task_id = fn()
                results[name] = task_id or 'dispatched'
            except Exception as e:
                results[name] = f'error: {e}'
        logger.info('LoyaltyJobRunner.run_all_daily_jobs: %s', results)
        return results


# Module-level singleton
jobs = LoyaltyJobRunner()
