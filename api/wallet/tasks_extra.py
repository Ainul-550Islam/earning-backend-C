# api/wallet/tasks_extra.py
"""
Extra Celery tasks for new world-class features.
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger("wallet.tasks_extra")


@shared_task(bind=True, max_retries=5, default_retry_delay=60, name="wallet.deliver_webhook")
def deliver_webhook(self, endpoint_id: int, payload: dict):
    """Deliver webhook with exponential backoff retry."""
    try:
        from .models_cpalead_extra import WebhookEndpoint
        from .services_extra import WebhookDeliveryService
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
        success = WebhookDeliveryService.deliver(endpoint.url, payload, endpoint.secret)
        endpoint.last_called_at = timezone.now()
        endpoint.last_status = 200 if success else 500
        if not success:
            endpoint.failure_count += 1
        endpoint.save(update_fields=["last_called_at","last_status","failure_count","updated_at"])
        return {"success": success, "endpoint": endpoint_id}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, name="wallet.process_mass_payout_job")
def process_mass_payout_job(self, job_id: int):
    """Process a MassPayoutJob in background."""
    try:
        from .services_extra import MassPayoutService
        result = MassPayoutService.process_job(job_id)
        logger.info(f"MassPayout job={job_id} done: {result}")
        return result
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, name="wallet.activate_whitelists")
def activate_whitelists(self):
    """Activate withdrawal addresses after 24h security hold (Binance-style). Run: every hour."""
    try:
        from .models_cpalead_extra import WithdrawalWhitelist
        cutoff = timezone.now() - timedelta(hours=24)
        pending = WithdrawalWhitelist.objects.filter(is_active=False, is_trusted=False, created_at__lte=cutoff)
        count = 0
        for wl in pending:
            wl.activate()
            count += 1
        logger.info(f"Activated {count} withdrawal whitelists")
        return {"activated": count}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, name="wallet.process_settlements")
def process_settlements(self):
    """Process T+1 and T+2 settlements. Run: daily at 9 AM."""
    try:
        from .models_cpalead_extra import SettlementBatch
        from datetime import date
        today = date.today()
        due = SettlementBatch.objects.filter(
            status="pending", settlement_date__lte=today
        ).select_related("wallet")
        processed = failed = 0
        for batch in due:
            try:
                batch.status = "settled"
                batch.settled_at = timezone.now()
                batch.save()
                processed += 1
            except Exception as e:
                logger.error(f"Settlement {batch.settlement_id}: {e}")
                batch.status = "failed"; batch.save()
                failed += 1
        return {"processed": processed, "failed": failed}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, name="wallet.generate_annual_tax_records")
def generate_annual_tax_records(self, year: int = None):
    """Generate tax records for all users for the given year. Run: Jan 1."""
    try:
        from .models import Wallet
        from .services_extra import TaxService
        import datetime
        yr = year or (datetime.date.today().year - 1)
        count = 0
        for wallet in Wallet.objects.select_related("user"):
            try:
                TaxService.generate(wallet.user, wallet, yr)
                count += 1
            except Exception as e:
                logger.error(f"Tax record {wallet.user.username} {yr}: {e}")
        return {"generated": count, "year": yr}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, name="wallet.run_aml_check")
def run_aml_check(self, user_id: int, wallet_id: int, amount: float, txn_type: str = "withdrawal"):
    """Run AML check on a transaction."""
    try:
        from decimal import Decimal
        from django.contrib.auth import get_user_model
        from .models import Wallet
        from .services_extra import AMLService
        user   = get_user_model().objects.get(id=user_id)
        wallet = Wallet.objects.get(id=wallet_id)
        flags  = AMLService.check(user, wallet, Decimal(str(amount)), txn_type)
        return {"flags": len(flags), "types": [f["type"] for f in flags]}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, name="wallet.reset_offer_daily_caps")
def reset_offer_daily_caps(self):
    """Reset daily conversion caps for all offers. Run: daily midnight."""
    try:
        from .models_cpalead_extra import EarningOffer
        count = EarningOffer.objects.filter(is_active=True).update(conversions_today=0)
        logger.info(f"Reset daily caps for {count} offers")
        return {"reset": count}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, name="wallet.auto_resolve_stale_disputes")
def auto_resolve_stale_disputes(self, days: int = 30):
    """Auto-close disputes not resolved in N days. Run: weekly."""
    try:
        from .models_cpalead_extra import DisputeCase
        cutoff = timezone.now() - timedelta(days=days)
        stale = DisputeCase.objects.filter(status__in=["open","under_review"], created_at__lt=cutoff)
        count = stale.update(status="resolved_platform", outcome="no_refund", resolved_at=timezone.now())
        logger.info(f"Auto-resolved {count} stale disputes")
        return {"resolved": count}
    except Exception as e:
        raise self.retry(exc=e)
