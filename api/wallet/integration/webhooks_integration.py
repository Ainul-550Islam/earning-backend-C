# api/wallet/integration/webhooks_integration.py
"""
Webhook integration — receive, verify, and dispatch gateway webhooks.
Supports: bKash, Nagad, Rocket, SSLCommerz, Stripe, PayPal, NowPayments.

Flow:
  Gateway → POST /api/wallet/webhook/{gateway}/ → receive_webhook()
          → WalletWebhookLog.create()
          → verify_signature()
          → process_webhook_async.delay()
            → dispatch_to_handler()
              → update withdrawal status
              → credit/debit wallet
              → fire events
"""
import hashlib
import hmac
import json
import logging
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

logger = logging.getLogger("wallet.integration.webhooks")


class WebhookVerifier:
    """Verify webhook signatures for each gateway."""

    @staticmethod
    def verify_bkash(payload: bytes, signature: str, secret: str) -> bool:
        """Verify bKash HMAC-SHA256 signature."""
        try:
            expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False

    @staticmethod
    def verify_stripe(payload: bytes, sig_header: str, secret: str) -> bool:
        """Verify Stripe webhook signature."""
        try:
            import stripe
            stripe.Webhook.construct_event(payload, sig_header, secret)
            return True
        except Exception:
            return False

    @staticmethod
    def verify_paypal(payload: bytes, transmission_sig: str,
                      cert_url: str, transmission_id: str) -> bool:
        """Verify PayPal webhook (basic check)."""
        return bool(transmission_sig and transmission_id)

    @staticmethod
    def verify_nowpayments(payload: bytes, signature: str, secret: str) -> bool:
        """Verify NowPayments IPN signature."""
        try:
            import hashlib
            expected = hashlib.sha512(secret.encode() + payload).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False


class WebhookDispatcher:
    """Route verified webhook payloads to appropriate handlers."""

    HANDLERS = {
        "bkash":       "handle_bkash",
        "nagad":       "handle_nagad",
        "rocket":      "handle_rocket",
        "sslcommerz":  "handle_sslcommerz",
        "stripe":      "handle_stripe",
        "paypal":      "handle_paypal",
        "nowpayments": "handle_nowpayments",
    }

    @classmethod
    def dispatch(cls, log_id: int, gateway: str, payload: dict) -> dict:
        """Dispatch webhook to appropriate handler."""
        handler_name = cls.HANDLERS.get(gateway)
        if not handler_name:
            logger.warning(f"No handler for gateway: {gateway}")
            return {"processed": False, "reason": f"Unknown gateway: {gateway}"}

        handler = getattr(cls, handler_name, None)
        if not handler:
            return {"processed": False, "reason": "Handler not implemented"}

        try:
            return handler(log_id, payload)
        except Exception as e:
            logger.error(f"Webhook dispatch error {gateway}: {e}", exc_info=True)
            return {"processed": False, "error": str(e)}

    @staticmethod
    def handle_bkash(log_id: int, payload: dict) -> dict:
        """Handle bKash B2C/payment callback."""
        status    = payload.get("transactionStatus", "")
        trx_id    = payload.get("trxID", "")
        gateway_ref = payload.get("paymentID", trx_id)

        if status in ("Completed", "Authorized"):
            return WebhookDispatcher._complete_withdrawal(gateway_ref, "bkash")
        elif status in ("Failed", "Expired", "Cancelled"):
            return WebhookDispatcher._fail_withdrawal(gateway_ref, f"bKash: {status}")
        return {"processed": True, "status": "ignored", "bkash_status": status}

    @staticmethod
    def handle_nagad(log_id: int, payload: dict) -> dict:
        """Handle Nagad callback."""
        status    = payload.get("reason", "")
        order_id  = payload.get("merchantOrderId", "")
        if status == "Successful":
            return WebhookDispatcher._complete_withdrawal(order_id, "nagad")
        return {"processed": True, "status": "ignored"}

    @staticmethod
    def handle_nowpayments(log_id: int, payload: dict) -> dict:
        """Handle NowPayments IPN for USDT payouts."""
        payment_status = payload.get("payment_status", "")
        payment_id     = str(payload.get("payment_id", ""))
        if payment_status in ("finished", "confirmed", "sending"):
            return WebhookDispatcher._complete_withdrawal(payment_id, "usdt")
        elif payment_status in ("failed", "expired", "refunded"):
            return WebhookDispatcher._fail_withdrawal(payment_id, f"USDT: {payment_status}")
        return {"processed": True, "status": "pending"}

    @staticmethod
    def handle_stripe(log_id: int, payload: dict) -> dict:
        """Handle Stripe Connect webhook events."""
        event_type = payload.get("type", "")
        obj        = payload.get("data", {}).get("object", {})
        if event_type == "payout.paid":
            payout_id = obj.get("id","")
            return WebhookDispatcher._complete_withdrawal(payout_id, "stripe")
        elif event_type == "payout.failed":
            payout_id    = obj.get("id","")
            failure_msg  = obj.get("failure_message","Failed")
            return WebhookDispatcher._fail_withdrawal(payout_id, failure_msg)
        return {"processed": True, "status": "event_ignored", "event": event_type}

    @staticmethod
    def handle_paypal(log_id: int, payload: dict) -> dict:
        """Handle PayPal Payouts webhook."""
        event_type = payload.get("event_type","")
        resource   = payload.get("resource",{})
        payout_id  = resource.get("payout_item_id","") or resource.get("sender_batch_id","")
        if "ITEM.UNCLAIMED" in event_type or "SUCCEEDED" in event_type:
            return WebhookDispatcher._complete_withdrawal(payout_id, "paypal")
        elif "FAILED" in event_type or "RETURNED" in event_type:
            return WebhookDispatcher._fail_withdrawal(payout_id, event_type)
        return {"processed": True, "status": "ignored"}

    @staticmethod
    def handle_rocket(log_id: int, payload: dict) -> dict:
        """Handle Rocket MFS callback."""
        status = payload.get("status","")
        ref_id = payload.get("reference_id","")
        if status == "SUCCESS":
            return WebhookDispatcher._complete_withdrawal(ref_id, "rocket")
        return {"processed": True}

    @staticmethod
    def handle_sslcommerz(log_id: int, payload: dict) -> dict:
        """Handle SSLCommerz IPN."""
        status  = payload.get("status","")
        val_id  = payload.get("val_id","")
        if status == "VALID":
            return WebhookDispatcher._complete_withdrawal(val_id, "sslcommerz")
        return {"processed": True}

    @staticmethod
    def _complete_withdrawal(gateway_ref: str, gateway: str) -> dict:
        """Mark withdrawal as completed."""
        try:
            from ..models.withdrawal import WithdrawalRequest
            from ..services.withdrawal.WithdrawalService import WithdrawalService
            wr = WithdrawalRequest.objects.filter(
                gateway_reference=gateway_ref, status__in=["approved","processing"]
            ).first()
            if wr:
                WithdrawalService.complete(wr, gateway_ref=gateway_ref)
                return {"processed": True, "withdrawal_id": str(wr.withdrawal_id)}
            return {"processed": True, "withdrawal_id": None, "note": "not found"}
        except Exception as e:
            logger.error(f"Complete withdrawal error: {e}")
            return {"processed": False, "error": str(e)}

    @staticmethod
    def _fail_withdrawal(gateway_ref: str, reason: str) -> dict:
        """Mark withdrawal as failed and refund."""
        try:
            from ..models.withdrawal import WithdrawalRequest
            from ..services.withdrawal.WithdrawalService import WithdrawalService
            wr = WithdrawalRequest.objects.filter(
                gateway_reference=gateway_ref, status__in=["approved","processing"]
            ).first()
            if wr:
                WithdrawalService.reject(wr, reason=f"Gateway: {reason}")
                return {"processed": True, "refunded": True}
            return {"processed": True, "withdrawal_id": None}
        except Exception as e:
            logger.error(f"Fail withdrawal error: {e}")
            return {"processed": False, "error": str(e)}
