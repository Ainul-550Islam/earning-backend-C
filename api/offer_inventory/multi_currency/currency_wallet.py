# api/offer_inventory/multi_currency/currency_wallet.py
"""
Multi-Currency Wallet — User can hold balance in multiple currencies.
All stored as Decimal. Conversion on-demand with live rates.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

P2 = Decimal('0.01')
P4 = Decimal('0.0001')

SUPPORTED_CURRENCIES = ['BDT', 'USD', 'EUR', 'GBP', 'INR', 'SGD', 'AED']
DEFAULT_CURRENCY      = 'BDT'


class MultiCurrencyWallet:
    """
    Multi-currency balance management.
    Each user has per-currency sub-wallets tracked in WalletTransaction.
    """

    @staticmethod
    def get_balances(user) -> dict:
        """Get balances in all currencies the user has earned in."""
        from api.offer_inventory.models import WalletTransaction, WalletAudit
        from django.db.models import Sum

        balances = {}
        for currency in SUPPORTED_CURRENCIES:
            credits = WalletTransaction.objects.filter(
                user=user, tx_type='credit', currency=currency
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            debits  = WalletTransaction.objects.filter(
                user=user, tx_type='debit', currency=currency
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            net = credits - debits
            if net > 0 or currency == DEFAULT_CURRENCY:
                balances[currency] = float(net.quantize(P2))

        return balances

    @staticmethod
    def get_total_in_currency(user, target_currency: str = 'BDT') -> Decimal:
        """Get total balance converted to a target currency."""
        from api.offer_inventory.multi_currency.exchange_engine import ExchangeEngine

        balances = MultiCurrencyWallet.get_balances(user)
        total    = Decimal('0')
        for currency, amount in balances.items():
            if currency == target_currency:
                total += Decimal(str(amount))
            else:
                converted = ExchangeEngine.convert(
                    Decimal(str(amount)), currency, target_currency
                )
                total += converted
        return total.quantize(P2, rounding=ROUND_HALF_UP)

    @staticmethod
    @transaction.atomic
    def credit(user, amount: Decimal, currency: str = 'BDT',
                source: str = 'conversion', source_id: str = '',
                description: str = '') -> object:
        """Credit wallet in a specific currency."""
        from api.offer_inventory.models import WalletTransaction

        currency = currency.upper()
        if currency not in SUPPORTED_CURRENCIES:
            currency = DEFAULT_CURRENCY

        return WalletTransaction.objects.create(
            user        =user,
            tx_type     ='credit',
            amount      =amount.quantize(P4, rounding=ROUND_HALF_UP),
            currency    =currency,
            source      =source,
            source_id   =source_id,
            description =description,
        )

    @staticmethod
    @transaction.atomic
    def debit(user, amount: Decimal, currency: str = 'BDT',
               source: str = 'withdrawal', source_id: str = '',
               description: str = '') -> object:
        """Debit wallet in a specific currency."""
        from api.offer_inventory.models import WalletTransaction

        currency  = currency.upper()
        available = MultiCurrencyWallet.get_balance(user, currency)
        if available < amount:
            from api.offer_inventory.exceptions import InsufficientBalanceException
            raise InsufficientBalanceException(
                f'Insufficient {currency} balance: {available} < {amount}'
            )

        return WalletTransaction.objects.create(
            user       =user,
            tx_type    ='debit',
            amount     =amount.quantize(P4, rounding=ROUND_HALF_UP),
            currency   =currency,
            source     =source,
            source_id  =source_id,
            description=description,
        )

    @staticmethod
    def get_balance(user, currency: str = 'BDT') -> Decimal:
        """Get balance for a specific currency."""
        from api.offer_inventory.models import WalletTransaction
        from django.db.models import Sum

        currency = currency.upper()
        credits  = WalletTransaction.objects.filter(
            user=user, tx_type='credit', currency=currency
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        debits   = WalletTransaction.objects.filter(
            user=user, tx_type='debit', currency=currency
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        return (credits - debits).quantize(P4, rounding=ROUND_HALF_UP)

    @staticmethod
    def exchange(user, amount: Decimal, from_currency: str,
                  to_currency: str) -> dict:
        """Exchange between currencies in user's wallet."""
        from api.offer_inventory.multi_currency.exchange_engine import ExchangeEngine

        converted = ExchangeEngine.convert(amount, from_currency, to_currency)
        MultiCurrencyWallet.debit(user, amount, from_currency, 'exchange', '', f'Exchange {from_currency}→{to_currency}')
        MultiCurrencyWallet.credit(user, converted, to_currency, 'exchange', '', f'Exchange {from_currency}→{to_currency}')
        return {
            'from_currency': from_currency,
            'to_currency'  : to_currency,
            'amount_deducted': float(amount),
            'amount_credited': float(converted),
            'rate'           : float(ExchangeEngine.get_rate(from_currency, to_currency)),
        }


# ─────────────────────────────────────────────────────
# exchange_engine.py
# ─────────────────────────────────────────────────────

class ExchangeEngine:
    """Real-time currency exchange using live rates with fallback."""

    @staticmethod
    def convert(amount: Decimal, from_c: str, to_c: str) -> Decimal:
        """Convert amount between currencies."""
        from api.offer_inventory.finance_payment.currency_converter_v2 import CurrencyConverterV2
        return CurrencyConverterV2.convert(amount, from_c, to_c)

    @staticmethod
    def get_rate(from_c: str, to_c: str) -> Decimal:
        """Get current exchange rate."""
        from api.offer_inventory.finance_payment.currency_converter_v2 import CurrencyConverterV2
        return CurrencyConverterV2.get_rate(from_c.upper(), to_c.upper())

    @staticmethod
    def get_all_rates(base: str = 'BDT') -> dict:
        """Get all rates relative to base currency."""
        from api.offer_inventory.finance_payment.currency_converter_v2 import CurrencyConverterV2
        rates = {}
        for currency in SUPPORTED_CURRENCIES:
            if currency != base:
                try:
                    rates[currency] = float(CurrencyConverterV2.get_rate(base, currency))
                except Exception:
                    pass
        return rates

    @staticmethod
    def get_payout_in_local(reward_bdt: Decimal, user_country: str) -> dict:
        """Convert BDT reward to user's local currency."""
        country_currency = {
            'BD': 'BDT', 'US': 'USD', 'GB': 'GBP',
            'IN': 'INR', 'DE': 'EUR', 'FR': 'EUR',
            'SG': 'SGD', 'AE': 'AED',
        }
        local_currency = country_currency.get(user_country.upper(), 'USD')
        if local_currency == 'BDT':
            return {'amount': float(reward_bdt), 'currency': 'BDT'}
        converted = ExchangeEngine.convert(reward_bdt, 'BDT', local_currency)
        return {
            'bdt_amount'    : float(reward_bdt),
            'local_amount'  : float(converted),
            'local_currency': local_currency,
        }
