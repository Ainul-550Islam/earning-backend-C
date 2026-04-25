# api/payment_gateways/integration_system/bridge.py
# Bridge — translates data between payment_gateways models and external app models

from decimal import Decimal
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class DataBridge:
    """
    Translates payment_gateways data structures to formats expected by
    your existing apps (api.wallet, api.analytics, api.notifications, etc.)

    Prevents coupling between payment_gateways and external apps.
    Each app speaks its own language — bridge translates between them.
    """

    # ── Wallet bridge ──────────────────────────────────────────────────────────
    def deposit_to_wallet_txn(self, deposit) -> dict:
        """Convert DepositRequest → api.wallet transaction format."""
        return {
            'user':             deposit.user,
            'transaction_type': 'credit',
            'amount':           deposit.net_amount,
            'currency':         deposit.currency,
            'source':           'gateway',
            'gateway':          deposit.gateway,
            'reference':        deposit.reference_id,
            'external_ref':     deposit.gateway_ref or '',
            'description':      f'Deposit via {deposit.gateway.upper()}',
            'metadata': {
                'gateway':          deposit.gateway,
                'gross_amount':     str(deposit.amount),
                'fee':              str(deposit.fee),
                'deposit_id':       deposit.id,
            }
        }

    def withdrawal_to_wallet_txn(self, payout_request) -> dict:
        """Convert PayoutRequest → api.wallet transaction format."""
        return {
            'user':             payout_request.user,
            'transaction_type': 'debit',
            'amount':           payout_request.net_amount,
            'currency':         payout_request.currency,
            'source':           'payout',
            'gateway':          payout_request.payout_method,
            'reference':        payout_request.reference_id,
            'description':      f'Withdrawal via {payout_request.payout_method.upper()}',
            'metadata': {
                'account':  payout_request.account_number[-4:],
                'payout_id':payout_request.id,
                'fee':      str(payout_request.fee),
            }
        }

    def conversion_to_wallet_txn(self, conversion) -> dict:
        """Convert Conversion → api.wallet transaction format."""
        offer_name = conversion.offer.name if conversion.offer else 'Offer Completion'
        return {
            'user':             conversion.publisher,
            'transaction_type': 'earning',
            'amount':           conversion.payout,
            'currency':         conversion.currency,
            'source':           'conversion',
            'reference':        conversion.conversion_id,
            'description':      f'Earned: {offer_name}',
            'metadata': {
                'offer_id':       conversion.offer_id,
                'conversion_type':conversion.conversion_type,
                'cost':           str(conversion.cost),
            }
        }

    # ── Notification bridge ────────────────────────────────────────────────────
    def deposit_to_notification(self, user, deposit) -> dict:
        """Convert deposit data to notification format."""
        return {
            'user':     user,
            'template': 'payment_deposit_completed',
            'subject':  f'Deposit Confirmed — {deposit.currency} {deposit.net_amount}',
            'context': {
                'amount':         str(deposit.net_amount),
                'currency':       deposit.currency,
                'gateway':        deposit.gateway.upper(),
                'reference':      deposit.reference_id,
                'date':           deposit.completed_at.strftime('%d %b %Y %I:%M %p') if deposit.completed_at else '',
                'user_name':      user.get_full_name() or user.username,
            },
            'channels': ['email', 'in_app', 'push'],
        }

    def withdrawal_to_notification(self, user, payout) -> dict:
        """Convert payout data to notification format."""
        return {
            'user':     user,
            'template': 'payment_withdrawal_processed',
            'subject':  f'Withdrawal Processed — {payout.currency} {payout.net_amount}',
            'context': {
                'amount':   str(payout.net_amount),
                'currency': payout.currency,
                'method':   payout.payout_method.upper(),
                'account':  payout.account_number[-4:],
                'reference':payout.reference_id,
            },
            'channels': ['email', 'in_app'],
        }

    # ── Analytics bridge ───────────────────────────────────────────────────────
    def deposit_to_analytics_event(self, deposit) -> dict:
        """Convert deposit to analytics event format."""
        return {
            'event_type': 'payment_deposit',
            'user_id':    deposit.user_id,
            'properties': {
                'gateway':    deposit.gateway,
                'amount':     float(deposit.amount),
                'fee':        float(deposit.fee),
                'net_amount': float(deposit.net_amount),
                'currency':   deposit.currency,
                'status':     deposit.status,
            },
            'timestamp': deposit.completed_at.isoformat() if deposit.completed_at else None,
        }

    def conversion_to_analytics_event(self, conversion) -> dict:
        """Convert conversion to analytics event."""
        return {
            'event_type': 'publisher_conversion',
            'user_id':    conversion.publisher_id,
            'properties': {
                'offer_id':       conversion.offer_id,
                'payout':         float(conversion.payout),
                'conversion_type':conversion.conversion_type,
                'country':        conversion.country_code,
                'device':         conversion.device_type,
            },
        }

    # ── Fraud bridge ───────────────────────────────────────────────────────────
    def fraud_result_to_fraud_event(self, user, transaction, result: dict) -> dict:
        """Convert fraud detection result to api.fraud_detection format."""
        return {
            'user':       user,
            'event_type': 'payment_fraud',
            'risk_score': result.get('risk_score', 0),
            'risk_level': result.get('risk_level', 'low'),
            'action':     result.get('action', 'flag'),
            'reasons':    result.get('reasons', []),
            'metadata': {
                'gateway':    getattr(transaction, 'gateway', ''),
                'amount':     str(getattr(transaction, 'amount', 0)),
                'reference':  getattr(transaction, 'reference_id', ''),
            },
        }

    # ── Generic bridge ─────────────────────────────────────────────────────────
    def normalize_amount(self, amount: Any, currency: str = 'USD') -> Decimal:
        """Normalize amount to Decimal regardless of input type."""
        try:
            return Decimal(str(amount)).quantize(Decimal('0.01'))
        except Exception:
            return Decimal('0')
