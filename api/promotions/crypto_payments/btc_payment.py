# =============================================================================
# promotions/crypto_payments/btc_payment.py
# Bitcoin Payout — MaxBounty / Zeydoo style BTC withdrawal
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
import uuid
import logging

logger = logging.getLogger(__name__)

BTC_MINIMUM = Decimal('50.00')  # $50 minimum for BTC


class BTCPaymentProcessor:
    """Bitcoin payout processor."""

    def create_btc_payout(self, publisher_id: int, amount_usd: Decimal, btc_address: str) -> dict:
        if amount_usd < BTC_MINIMUM:
            return {'error': f'Minimum BTC payout is ${BTC_MINIMUM}'}

        if not self._validate_btc_address(btc_address):
            return {'error': 'Invalid Bitcoin address'}

        btc_rate = self._get_btc_rate()
        btc_amount = amount_usd / btc_rate if btc_rate > 0 else Decimal('0')
        network_fee_btc = Decimal('0.0001')
        net_btc = btc_amount - network_fee_btc

        payout_id = str(uuid.uuid4())
        payout = {
            'payout_id': payout_id,
            'publisher_id': publisher_id,
            'amount_usd': str(amount_usd),
            'btc_amount': str(btc_amount.quantize(Decimal('0.00000001'))),
            'net_btc': str(net_btc.quantize(Decimal('0.00000001'))),
            'btc_address': btc_address,
            'btc_rate': str(btc_rate),
            'status': 'pending',
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'btc_payout:{payout_id}', payout, timeout=3600 * 24 * 7)

        return {
            'payout_id': payout_id,
            'amount_usd': str(amount_usd),
            'btc_amount': str(net_btc.quantize(Decimal('0.00000001'))),
            'btc_rate': str(btc_rate),
            'address': f'{btc_address[:6]}...{btc_address[-4:]}',
            'estimated_time': '1-3 hours',
            'status': 'pending',
        }

    def _get_btc_rate(self) -> Decimal:
        """Get current BTC/USD rate from cache."""
        rate = cache.get('btc_usd_rate')
        if rate:
            return Decimal(str(rate))
        return Decimal('65000')  # Fallback rate

    def _validate_btc_address(self, address: str) -> bool:
        return len(address) >= 26 and len(address) <= 62 and address[0] in ('1', '3', 'b')
