# api/wallet/tasks/currency_tasks.py
import logging
from celery import shared_task

logger = logging.getLogger("wallet.tasks.currency")


@shared_task(bind=True, max_retries=3, name="wallet.update_exchange_rates")
def update_exchange_rates(self):
    """Update all exchange rates — run every hour."""
    try:
        from ..currency_converter import CurrencyConverter
        updated = CurrencyConverter.update_all_rates()
        logger.info(f"Exchange rates updated: {len(updated)} currencies")
        return {"updated": len(updated), "currencies": list(updated.keys())}
    except Exception as e:
        raise self.retry(exc=e, countdown=300)


@shared_task(name="wallet.get_bdt_usd_rate")
def get_bdt_usd_rate():
    """Fetch and cache BDT/USD rate specifically."""
    try:
        from ..currency_converter import CurrencyConverter
        rate = CurrencyConverter.get_rate_to_bdt("USD")
        logger.info(f"BDT/USD rate: {rate}")
        return {"rate": float(rate), "currency": "USD/BDT"}
    except Exception as e:
        return {"error": str(e)}
