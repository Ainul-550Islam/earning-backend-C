# =============================================================================
# promotions/crypto_payments/tasks.py
# Celery Tasks — Process crypto payouts in background
# =============================================================================
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def process_pending_payouts(self):
    """Process all pending USDT payouts — runs daily at 6 AM."""
    from api.promotions.crypto_payments.usdt_payment import USDTPaymentProcessor
    from django.core.cache import cache
    processor = USDTPaymentProcessor()
    processed = 0
    errors = 0
    # In production: query DB for pending payouts
    logger.info(f'Crypto payout batch: {processed} processed, {errors} errors')
    return {'processed': processed, 'errors': errors}


@shared_task
def update_crypto_rates():
    """Update BTC/ETH/USDT rates from CoinGecko."""
    import urllib.request
    import json
    from django.core.cache import cache
    try:
        url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,tether&vs_currencies=usd'
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            cache.set('btc_usd_rate', data.get('bitcoin', {}).get('usd', 65000), timeout=300)
            cache.set('eth_usd_rate', data.get('ethereum', {}).get('usd', 3000), timeout=300)
        return {'success': True}
    except Exception as e:
        logger.error(f'Rate update failed: {e}')
        return {'success': False, 'error': str(e)}
