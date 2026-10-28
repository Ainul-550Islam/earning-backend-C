# api/referral/tasks/clawback_tasks.py
# Celery tasks: process approved commission clawbacks
# ============================================================

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.process_approved_clawbacks',
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def process_approved_clawbacks(self, dry_run: bool = False):
    """
    Approved clawbacks process করো।
    প্রতিদিন সকালে run হয়।

    Schedule example:
        'referral-process-clawbacks': {
            'task': 'referral.process_approved_clawbacks',
            'schedule': crontab(hour=1, minute=0),  # 1 AM daily
        }
    """
    try:
        from api.referral.services.CommissionClawbackService import (
            CommissionClawbackService,
        )

        result = CommissionClawbackService.process_all_approved(
            dry_run=dry_run
        )

        logger.info(
            f"[Task] process_approved_clawbacks: "
            f"processed={result['processed']}, "
            f"total_clawed={result['total_clawed']}, "
            f"errors={result['errors']}, "
            f"dry_run={dry_run}"
        )

        return result

    except Exception as exc:
        logger.error(f"[Task] process_approved_clawbacks failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.initiate_fraud_clawbacks',
    bind=True,
    max_retries=2,
)
def initiate_fraud_clawbacks(self):
    """
    Newly confirmed fraud referrals এ clawback initiate করো।
    Fraud confirm হওয়ার পরে auto-initiate।

    Schedule example:
        'referral-initiate-fraud-clawbacks': {
            'task': 'referral.initiate_fraud_clawbacks',
            'schedule': crontab(hour=2, minute=30),
        }
    """
    try:
        from api.referral.models import SuspiciousReferral, CommissionClawback
        from api.referral.services.CommissionClawbackService import (
            CommissionClawbackService,
        )

        # Confirmed fraud referrals without clawback initiated yet
        fraud_referrals = SuspiciousReferral.objects.filter(
            status='fraud',
        ).select_related('referral')

        initiated = 0
        skipped = 0

        for sr in fraud_referrals:
            # Check if clawback already initiated
            existing = CommissionClawback.objects.filter(
                commission__referred_user=sr.referral.referred_user,
            ).exists()

            if existing:
                skipped += 1
                continue

            result = CommissionClawbackService.bulk_initiate_for_fraud(
                referral_id=sr.referral.id,
                reason_detail=f"Confirmed fraud: {', '.join(sr.get_flag_list())}",
            )
            initiated += result.get('initiated', 0)

        logger.info(
            f"[Task] initiate_fraud_clawbacks: "
            f"initiated={initiated}, skipped={skipped}"
        )

        return {'initiated': initiated, 'skipped': skipped}

    except Exception as exc:
        logger.error(f"[Task] initiate_fraud_clawbacks failed: {exc}")
        raise self.retry(exc=exc)