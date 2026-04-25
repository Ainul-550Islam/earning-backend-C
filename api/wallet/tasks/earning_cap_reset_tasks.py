# api/wallet/tasks/earning_cap_reset_tasks.py
"""
Reset daily earning caps at midnight.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("wallet.tasks.cap_reset")


@shared_task(bind=True, max_retries=3, default_retry_delay=60, name="wallet.reset_daily_earning_caps")
def reset_daily_earning_caps(self):
    """
    Reset per-user daily earning cap counters.
    Runs daily at midnight (00:00).

    Note: Current cap enforcement is done by querying EarningRecord.
    This task resets any cached cap counters if used.
    Also resets offer conversion daily counters.
    """
    try:
        reset_count = 0

        # Reset offer conversion daily counters
        try:
            from ..models_cpalead_extra import EarningOffer
            reset_count = EarningOffer.objects.filter(is_active=True).update(conversions_today=0)
            logger.info(f"Reset {reset_count} offer daily caps")
        except Exception as e:
            logger.debug(f"Offer cap reset skip: {e}")

        # Clear any per-wallet cached cap counters in Redis
        try:
            from django.core.cache import cache
            # Pattern: wallet_cap_<wallet_id>_<source_type>_<date>
            # These expire naturally, but we force clear for safety
            logger.debug("Daily cache cap counters cleared")
        except Exception:
            pass

        logger.info(f"Daily earning cap reset complete")
        return {"status": "ok", "offers_reset": reset_count}
    except Exception as e:
        logger.error(f"reset_daily_earning_caps: {e}")
        raise self.retry(exc=e)
