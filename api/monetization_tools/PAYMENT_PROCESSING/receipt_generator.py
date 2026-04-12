"""PAYMENT_PROCESSING/receipt_generator.py — Payment receipt generation."""
from decimal import Decimal


class ReceiptGenerator:
    """Generates payment receipts after successful transactions."""

    @classmethod
    def generate(cls, transaction) -> dict:
        return {
            "receipt_id":       f"RCT-{transaction.txn_id}",
            "transaction_id":   str(transaction.txn_id),
            "gateway":          transaction.gateway,
            "amount":           str(transaction.amount),
            "currency":         transaction.currency,
            "purpose":          transaction.purpose,
            "status":           transaction.status,
            "user_id":          transaction.user_id,
            "paid_at":          str(transaction.completed_at) if transaction.completed_at else None,
        }

    @classmethod
    def for_payout(cls, payout_request) -> dict:
        return {
            "receipt_id":    f"PAY-{payout_request.request_id}",
            "request_id":    str(payout_request.request_id),
            "amount":        str(payout_request.net_amount),
            "currency":      payout_request.currency,
            "method":        payout_request.payout_method.method_type,
            "account":       payout_request.payout_method.account_number[-4:],
            "status":        payout_request.status,
            "paid_at":       str(payout_request.paid_at) if payout_request.paid_at else None,
        }
