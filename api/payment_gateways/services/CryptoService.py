# api/payment_gateways/services/CryptoService.py
# Cryptocurrency payment processor via Coinbase Commerce

import requests
import hmac
import hashlib
import json
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .PaymentProcessor import PaymentProcessor
import logging

logger = logging.getLogger(__name__)


class CryptoService(PaymentProcessor):
    """
    Cryptocurrency payment processor via Coinbase Commerce.

    Supported coins:
        BTC  — Bitcoin
        ETH  — Ethereum
        USDT — Tether (USD Tether)
        USDC — USD Coin
        LTC  — Litecoin
        BCH  — Bitcoin Cash

    Flow:
        1. Create a charge → user gets wallet address + amount
        2. User sends crypto
        3. Coinbase webhook confirms → balance credited in USD equivalent

    Docs: https://docs.cloud.coinbase.com/commerce/docs
    """

    COINBASE_API    = 'https://api.commerce.coinbase.com'
    API_VERSION     = '2018-03-22'

    SUPPORTED_COINS = ['BTC', 'ETH', 'USDT', 'USDC', 'LTC', 'BCH']

    def __init__(self):
        super().__init__('crypto')
        self.api_key     = getattr(settings, 'COINBASE_COMMERCE_API_KEY', '')
        self.webhook_secret = getattr(settings, 'COINBASE_WEBHOOK_SECRET', '')

    def _headers(self) -> dict:
        return {
            'X-CC-Api-Key':      self.api_key,
            'X-CC-Version':      self.API_VERSION,
            'Content-Type':      'application/json',
        }

    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """
        Create a Coinbase Commerce charge for crypto deposit.

        Args:
            amount: Amount in USD equivalent
            kwargs['coin']: Preferred coin (BTC, ETH, etc.) — optional
        """
        self.validate_amount(amount)

        txn = self.create_transaction(
            user=user,
            transaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata=kwargs.get('metadata', {})
        )

        try:
            payload = {
                'name':         'Deposit',
                'description':  f'Account deposit for user {user.id}',
                'local_price': {
                    'amount':   str(amount),
                    'currency': 'USD',
                },
                'pricing_type': 'fixed_price',
                'metadata': {
                    'user_id':      str(user.id),
                    'reference_id': txn.reference_id,
                    'email':        user.email,
                },
                'redirect_url': getattr(settings, 'CRYPTO_SUCCESS_URL', ''),
                'cancel_url':   getattr(settings, 'CRYPTO_CANCEL_URL', ''),
            }

            response = requests.post(
                f'{self.COINBASE_API}/charges',
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            charge_data = response.json().get('data', {})

            charge_id = charge_data.get('id', '')
            hosted_url = charge_data.get('hosted_url', '')

            txn.gateway_reference = charge_id
            txn.metadata['charge_data']   = charge_data
            txn.metadata['hosted_url']    = hosted_url
            txn.metadata['addresses']     = charge_data.get('addresses', {})
            txn.metadata['pricing']       = charge_data.get('pricing', {})
            txn.save()

            # Build address list for display
            addresses = charge_data.get('addresses', {})
            pricing   = charge_data.get('pricing', {})

            coin_options = []
            for coin in self.SUPPORTED_COINS:
                if coin in addresses and coin in pricing:
                    coin_options.append({
                        'coin':    coin,
                        'address': addresses[coin],
                        'amount':  pricing[coin]['amount'] if isinstance(pricing.get(coin), dict) else pricing.get(coin, ''),
                    })

            logger.info(f'Crypto charge created: {charge_id} user={user.id}')

            return {
                'transaction':   txn,
                'payment_url':   hosted_url,
                'charge_id':     charge_id,
                'coin_options':  coin_options,
                'expires_at':    charge_data.get('expires_at', ''),
                'message':       'Send crypto to any of the addresses below. Expires in 1 hour.',
            }

        except Exception as e:
            txn.status = 'failed'
            txn.metadata['error'] = str(e)
            txn.save()
            raise Exception(f'Crypto deposit failed: {str(e)}')

    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """
        Crypto withdrawal — send crypto to user's wallet address.
        Uses Coinbase Commerce payout API or manual process.
        """
        self.validate_amount(amount)

        from api.payment_gateways.models import PayoutRequest

        wallet_address = getattr(payment_method, 'account_number', kwargs.get('wallet_address', ''))
        coin           = kwargs.get('coin', 'USDT')

        if not wallet_address:
            raise ValueError('Wallet address is required for crypto withdrawal.')

        payout = PayoutRequest.objects.create(
            user           = user,
            amount         = amount,
            fee            = self.calculate_fee(amount),
            net_amount     = amount - self.calculate_fee(amount),
            payout_method  = 'crypto',
            account_number = wallet_address,
            account_name   = f'{coin} wallet',
            status         = 'pending',
            reference_id   = self.generate_reference_id(),
        )

        txn = self.create_transaction(
            user=user,
            transaction_type='withdrawal',
            amount=amount,
            payment_method=payment_method,
            metadata={
                'payout_id':      payout.id,
                'wallet_address': wallet_address,
                'coin':           coin,
            }
        )

        return {
            'transaction': txn,
            'payout':      payout,
            'message':     f'Crypto withdrawal ({coin}) submitted. Admin will process within 24 hours.',
        }

    def verify_payment(self, charge_id: str, **kwargs):
        """Verify Coinbase Commerce charge status."""
        try:
            response = requests.get(
                f'{self.COINBASE_API}/charges/{charge_id}',
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            charge = response.json().get('data', {})

            timeline = charge.get('timeline', [])
            status_map = {
                'COMPLETED':  'completed',
                'CONFIRMED':  'completed',
                'PENDING':    'processing',
                'UNRESOLVED': 'processing',
                'EXPIRED':    'failed',
                'CANCELED':   'cancelled',
            }

            latest_status = timeline[-1].get('status', '') if timeline else ''
            internal_status = status_map.get(latest_status, 'processing')

            from api.payment_gateways.models import GatewayTransaction
            try:
                txn        = GatewayTransaction.objects.get(gateway_reference=charge_id)
                txn.status = internal_status
                if internal_status == 'completed':
                    txn.completed_at = timezone.now()
                    user = txn.user
                    if hasattr(user, 'balance'):
                        user.balance += txn.net_amount
                        user.save(update_fields=['balance'])
                txn.metadata['charge_status'] = charge
                txn.save()
                return txn
            except GatewayTransaction.DoesNotExist:
                return None

        except Exception as e:
            raise Exception(f'Crypto verification failed: {str(e)}')

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        """Verify Coinbase Commerce webhook signature."""
        try:
            expected = hmac.new(
                self.webhook_secret.encode(),
                raw_body,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False

    def get_payment_url(self, transaction, **kwargs):
        return transaction.metadata.get('hosted_url')

    def get_charge_status(self, charge_id: str) -> str:
        """Quick status check for a charge."""
        try:
            response = requests.get(
                f'{self.COINBASE_API}/charges/{charge_id}',
                headers=self._headers(),
                timeout=10,
            )
            data     = response.json().get('data', {})
            timeline = data.get('timeline', [])
            return timeline[-1].get('status', 'UNKNOWN') if timeline else 'UNKNOWN'
        except Exception:
            return 'UNKNOWN'
