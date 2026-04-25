# api/wallet/tasks_cap.py
"""
CPAlead-specific Celery tasks (CAP = CPAlead Publisher).
Separate from tasks.py to keep concerns clean.
"""
import logging
from celery import shared_task
from datetime import date, timedelta

logger = logging.getLogger("wallet.tasks_cap")


@shared_task(bind=True, max_retries=3, name="wallet_cap.process_daily_payouts")
def process_daily_payouts(self):
    """CPAlead daily auto-payout — earn $1+ → paid next day. Run: 00:05."""
    try:
        from .services.earning.PayoutService import PayoutService
        result = PayoutService.process_daily_payouts()
        logger.info(f"Daily payouts: {result}")
        return result
    except Exception as e:
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=2, name="wallet_cap.release_publisher_holds")
def release_publisher_holds(self):
    """Release new publisher 30-day fund hold. Run: 02:00 daily."""
    try:
        from .services.earning.PayoutService import PayoutService
        count = PayoutService.release_holds()
        logger.info(f"Released {count} publisher holds")
        return {"released": count}
    except Exception as e:
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=2, name="wallet_cap.check_publisher_upgrades")
def check_publisher_upgrades(self):
    """Auto-upgrade publisher level. Run: 03:00 daily."""
    try:
        from .models_cpalead_extra import PublisherLevel
        upgraded = 0
        for pl in PublisherLevel.objects.filter(level__lt=5).select_related("user","wallet"):
            try:
                if pl.can_upgrade() and pl.upgrade():
                    upgraded += 1
                    logger.info(f"Publisher upgraded: {pl.user.username} → L{pl.level}")
            except Exception:
                pass
        return {"upgraded": upgraded}
    except Exception as e:
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=2, name="wallet_cap.reset_offer_daily_caps")
def reset_offer_daily_caps(self):
    """Reset CPAlead offer daily conversion caps. Run: 00:01 daily."""
    try:
        from .models_cpalead_extra import EarningOffer
        updated = EarningOffer.objects.filter(is_active=True).update(conversions_today=0)
        return {"reset": updated}
    except Exception as e:
        raise self.retry(exc=e, countdown=120)


@shared_task(bind=True, max_retries=2, name="wallet_cap.award_top_earner_bonuses")
def award_top_earner_bonuses(self):
    """Award top 5% earner performance bonuses. Run: 1st of month 01:00."""
    try:
        from .services.earning.PayoutService import PayoutService
        awarded = PayoutService.award_top_earner_bonuses()
        return {"awarded": awarded}
    except Exception as e:
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=2, name="wallet_cap.expire_referral_programs")
def expire_referral_programs(self):
    """Expire CPAlead 6-month referral programs. Run: 03:00 daily."""
    try:
        from django.utils import timezone
        from .models_cpalead_extra import ReferralProgram
        expired = ReferralProgram.objects.filter(
            is_active=True, expires_at__lt=timezone.now()
        ).update(is_active=False)
        return {"expired": expired}
    except Exception as e:
        raise self.retry(exc=e, countdown=300)
