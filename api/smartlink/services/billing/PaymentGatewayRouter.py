"""
SmartLink — Payment Gateway Router
===================================
Central dispatcher. Routes a PayoutRecord to the correct payment
gateway service based on the publisher's payment_method.

Supported gateways (all self-contained inside smartlink/services/billing/):
  - PayPal  → PayPalPayoutService
  - Wise    → WisePayoutService

Unsupported gateways (wire, crypto, payoneer) return a structured
"manual" result — the admin must process these externally and
call mark_paid() with the transaction reference.

No imports from any other api.* app.
"""
import logging
from .PayPalPayoutService import PayPalPayoutService
from .WisePayoutService import WisePayoutService

logger = logging.getLogger("smartlink.billing.gateway_router")


class PaymentGatewayRouter:
    """
    Routes a PayoutRecord to the correct payment gateway.

    Usage:
        router = PaymentGatewayRouter()
        result = router.process(payout_record)
    """

    # Gateway method strings (must match PayoutRecord.PaymentMethod choices)
    PAYPAL   = "paypal"
    WISE     = "wise"
    WIRE     = "wire"
    CRYPTO   = "crypto"
    PAYONEER = "payoneer"

    # Methods that require manual processing (no API integration yet)
    MANUAL_METHODS = {WIRE, CRYPTO, PAYONEER}

    def process(self, payout_record) -> dict:
        """
        Dispatch payout to the correct gateway and return a unified result dict.

        Unified result schema:
        {
            "success":          bool,
            "gateway":          str,           # "paypal" | "wise" | "manual"
            "transaction_id":   str,           # external reference from gateway
            "status":           str,           # "PENDING" | "PROCESSING" | "FAILED" | "MANUAL"
            "error":            str,           # empty string on success
            "requires_manual":  bool,          # True for wire/crypto/payoneer
        }
        """
        method = (payout_record.payment_method or "").lower()
        logger.info(
            f"PaymentGatewayRouter: ref={payout_record.reference_id} "
            f"method={method} amount={payout_record.net_amount}"
        )

        if method == self.PAYPAL:
            return self._run_paypal(payout_record)

        if method == self.WISE:
            return self._run_wise(payout_record)

        if method in self.MANUAL_METHODS:
            return self._manual(method)

        # Unknown method — treat as manual
        logger.warning(f"Unknown payment method '{method}' — treating as manual")
        return self._manual(method or "unknown")

    # ── Gateway runners ───────────────────────────────────────────────────────

    def _run_paypal(self, payout_record) -> dict:
        svc    = PayPalPayoutService()
        result = svc.send_payout(payout_record)
        return {
            "success":         result["success"],
            "gateway":         "paypal",
            "transaction_id":  result.get("transaction_id", ""),
            "status":          result.get("status", "FAILED"),
            "error":           result.get("error", ""),
            "requires_manual": False,
            "raw":             result,
        }

    def _run_wise(self, payout_record) -> dict:
        svc    = WisePayoutService()
        result = svc.send_payout(payout_record)
        return {
            "success":         result["success"],
            "gateway":         "wise",
            "transaction_id":  result.get("transaction_id", ""),
            "status":          result.get("status", "FAILED"),
            "error":           result.get("error", ""),
            "requires_manual": False,
            "raw":             result,
        }

    @staticmethod
    def _manual(method: str) -> dict:
        return {
            "success":         False,
            "gateway":         "manual",
            "transaction_id":  "",
            "status":          "MANUAL",
            "error":           (
                f"Payment method '{method}' requires manual processing. "
                "Process externally and call mark_paid() with the transaction reference."
            ),
            "requires_manual": True,
            "raw":             {},
        }
