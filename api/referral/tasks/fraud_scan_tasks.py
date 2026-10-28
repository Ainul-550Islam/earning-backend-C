# api/referral/tasks/fraud_scan_tasks.py
# Celery tasks: daily fraud detection scan
# ============================================================

from celery import shared_task
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.daily_fraud_scan',
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def daily_fraud_scan(self):
    """
    Existing referrals এর daily fraud scan।
    প্রতিদিন রাত ৩টায় run হয়।

    Schedule example:
        'referral-daily-fraud-scan': {
            'task': 'referral.daily_fraud_scan',
            'schedule': crontab(hour=3, minute=0),
        }
    """
    try:
        from api.referral.services.ReferralFraudService import (
            ReferralFraudService,
        )

        result = ReferralFraudService.scan_existing_referrals()

        logger.info(
            f"[Task] daily_fraud_scan: "
            f"scanned={result['scanned']}, "
            f"flagged={result['flagged']}"
        )

        # Admin notify if many flagged
        if result['flagged'] >= 10:
            _notify_admin_high_fraud.delay(
                flagged=result['flagged'],
                scanned=result['scanned'],
            )

        return result

    except Exception as exc:
        logger.error(f"[Task] daily_fraud_scan failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.notify_admin_high_fraud',
    bind=True,
    max_retries=1,
)
def _notify_admin_high_fraud(self, flagged: int, scanned: int):
    """Admin দের high fraud rate alert পাঠাও।"""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        fraud_rate = round((flagged / scanned) * 100, 2) if scanned else 0
        message = (
            f"High fraud rate detected: {flagged}/{scanned} referrals flagged "
            f"({fraud_rate}%). Please review the fraud queue."
        )

        # Notify all admin users
        admins = User.objects.filter(is_staff=True, is_active=True)
        for admin in admins:
            try:
                from api.notifications.services import NotificationService
                NotificationService.create(
                    user=admin,
                    notification_type='fraud_alert',
                    title='⚠️ High Fraud Rate Alert',
                    message=message,
                    data={
                        'flagged': flagged,
                        'scanned': scanned,
                        'fraud_rate': fraud_rate,
                    }
                )
            except ImportError:
                logger.warning(f"Admin fraud alert (no notification service): {message}")

        return {'notified_admins': admins.count()}

    except Exception as exc:
        logger.error(f"[Task] notify_admin_high_fraud failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.expire_blacklist_entries',
    bind=True,
    max_retries=2,
)
def expire_blacklist_entries(self):
    """
    Expired blacklist entries deactivate করো।
    প্রতিদিন ভোরে run হয়।

    Schedule example:
        'referral-expire-blacklist': {
            'task': 'referral.expire_blacklist_entries',
            'schedule': crontab(hour=4, minute=0),
        }
    """
    try:
        from api.referral.models import ReferralBlacklist
        from django.utils import timezone

        expired = ReferralBlacklist.objects.filter(
            is_active=True,
            expires_at__lt=timezone.now(),
        )

        count = expired.count()
        expired.update(is_active=False)

        logger.info(f"[Task] expire_blacklist_entries: expired={count}")
        return {'expired': count}

    except Exception as exc:
        logger.error(f"[Task] expire_blacklist_entries failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.auto_clear_low_risk_suspicious',
    bind=True,
    max_retries=2,
)
def auto_clear_low_risk_suspicious(self, max_score: int = 25):
    """
    Low fraud score suspicious referrals auto-clear করো।
    Score <= max_score এবং 7 দিনের বেশি পুরনো।

    Schedule example:
        'referral-auto-clear-low-risk': {
            'task': 'referral.auto_clear_low_risk_suspicious',
            'schedule': crontab(hour=5, minute=0, day_of_week=1),  # Weekly Monday
        }
    """
    try:
        from api.referral.models import SuspiciousReferral
        from django.utils import timezone
        from django.contrib.auth import get_user_model

        User = get_user_model()
        cutoff = timezone.now() - timedelta(days=7)

        low_risk = SuspiciousReferral.objects.filter(
            status='pending',
            fraud_score__lte=max_score,
            detected_at__lt=cutoff,
        )

        count = low_risk.count()

        # Get a system admin user for auto-clear
        system_admin = User.objects.filter(is_superuser=True).first()

        for sr in low_risk:
            try:
                sr.clear(
                    admin_user=system_admin,
                    notes=f"Auto-cleared: low risk score ({sr.fraud_score}) after 7 days"
                )
            except Exception as e:
                logger.warning(f"Auto-clear failed for suspicious {sr.id}: {e}")

        logger.info(
            f"[Task] auto_clear_low_risk_suspicious: "
            f"cleared={count}, max_score={max_score}"
        )
        return {'cleared': count}

    except Exception as exc:
        logger.error(f"[Task] auto_clear_low_risk_suspicious failed: {exc}")
        raise self.retry(exc=exc)