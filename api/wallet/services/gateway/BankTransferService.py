# api/wallet/services/gateway/BankTransferService.py
"""
BankTransferService — Bangladesh inter-bank transfer (NPSB/BEFTN/RTGS).

Supports:
  NPSB  — National Payment Switch Bangladesh (real-time, < 100k BDT)
  BEFTN — Bangladesh Electronic Funds Transfer Network (batch, < 500k BDT)
  RTGS  — Real Time Gross Settlement (high-value, ≥ 100k BDT)

Routing logic (auto-select):
  amount < 100,000 BDT  → NPSB (instant)
  100,000–500,000 BDT   → BEFTN (next business day)
  > 500,000 BDT         → RTGS (same day, high-value)

All arithmetic uses Decimal. No external module calls from this file.
"""
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from ...engine.circuit_breaker import get_breaker
from ...exceptions import GatewayError, InvalidAmountError

logger = logging.getLogger("wallet.gateway.bank_transfer")

# ── Routing thresholds (BDT) ─────────────────────────────────────
NPSB_LIMIT   = Decimal("100000")   # < 100k → NPSB
BEFTN_LIMIT  = Decimal("500000")   # 100k–500k → BEFTN
# > 500k → RTGS

# ── Standard fees ────────────────────────────────────────────────
NPSB_FEE     = Decimal("15.00")    # flat BDT
BEFTN_FEE    = Decimal("25.00")
RTGS_FEE_PCT = Decimal("0.0005")   # 0.05% of amount, min 200 BDT
RTGS_FEE_MIN = Decimal("200.00")

# ── Gateway names (for circuit breaker) ─────────────────────────
GW_NPSB  = "bank_npsb"
GW_BEFTN = "bank_beftn"
GW_RTGS  = "bank_rtgs"


class BankTransferService:
    """
    Inter-bank transfer service for Bangladesh banking rails.
    Auto-selects NPSB / BEFTN / RTGS based on amount.
    """

    # ── Public API ────────────────────────────────────────────────

    @classmethod
    def disburse(
        cls,
        receiver: str,
        amount: Decimal,
        reference: str,
        bank_code: str = "",
        account_name: str = "",
        branch_code: str = "",
    ) -> dict:
        """
        Initiate bank transfer. Auto-selects rail by amount.

        Args:
            receiver:     Bank account number (digits only)
            amount:       BDT amount (Decimal)
            reference:    Internal reference (withdrawal_id)
            bank_code:    9-digit Bangladesh bank routing code
            account_name: Account holder name
            branch_code:  Branch routing code (BEFTN/RTGS)

        Returns:
            {transaction_id, rail, fee, status, estimated_arrival}
        """
        amount = Decimal(str(amount))
        if amount <= Decimal("0"):
            raise InvalidAmountError("Bank transfer amount must be positive")

        rail = cls._select_rail(amount)
        fee  = cls._calculate_fee(amount, rail)
        gw   = cls._gateway_name(rail)

        # Circuit breaker
        breaker = get_breaker(gw)
        breaker.assert_closed()

        try:
            txn_id = str(uuid.uuid4()).replace("-", "")[:24]
            result = cls._send(
                rail=rail,
                receiver=receiver,
                amount=amount,
                fee=fee,
                reference=reference,
                bank_code=bank_code,
                account_name=account_name,
                branch_code=branch_code,
                txn_id=txn_id,
            )
            breaker.record_success()
            return result

        except GatewayError:
            breaker.record_failure()
            raise
        except Exception as e:
            breaker.record_failure()
            raise GatewayError(f"BankTransfer [{rail}] failed: {e}") from e

    @staticmethod
    def calculate_fee(amount: Decimal, rail: str = "") -> Decimal:
        """Public fee calculator. If rail not specified, auto-selects."""
        amount = Decimal(str(amount))
        if not rail:
            rail = BankTransferService._select_rail(amount)
        return BankTransferService._calculate_fee(amount, rail)

    @staticmethod
    def validate_account(account_number: str, bank_code: str = "") -> bool:
        """Basic validation: Bangladesh bank accounts are 13–17 digits."""
        clean = account_number.replace(" ", "").replace("-", "")
        if not clean.isdigit():
            return False
        if not (13 <= len(clean) <= 17):
            return False
        return True

    # ── Private helpers ──────────────────────────────────────────

    @staticmethod
    def _select_rail(amount: Decimal) -> str:
        """Auto-select banking rail by amount."""
        if amount < NPSB_LIMIT:
            return "NPSB"
        if amount <= BEFTN_LIMIT:
            return "BEFTN"
        return "RTGS"

    @staticmethod
    def _gateway_name(rail: str) -> str:
        return {
            "NPSB":  GW_NPSB,
            "BEFTN": GW_BEFTN,
            "RTGS":  GW_RTGS,
        }.get(rail, GW_NPSB)

    @staticmethod
    def _calculate_fee(amount: Decimal, rail: str) -> Decimal:
        if rail == "NPSB":
            return NPSB_FEE
        if rail == "BEFTN":
            return BEFTN_FEE
        # RTGS: 0.05% of amount, minimum 200 BDT
        return max(amount * RTGS_FEE_PCT, RTGS_FEE_MIN).quantize(Decimal("0.01"))

    @staticmethod
    def _estimated_arrival(rail: str) -> str:
        """Human-readable estimated arrival time."""
        now = timezone.now()
        if rail == "NPSB":
            return "Instant (within 30 minutes)"
        if rail == "BEFTN":
            return "Next business day"
        return "Same day (within 4 hours, before 3 PM)"

    @classmethod
    def _send(
        cls, rail, receiver, amount, fee,
        reference, bank_code, account_name,
        branch_code, txn_id,
    ) -> dict:
        """
        Send the actual transfer request to the Bangladesh banking API.
        In production: replace with real BB-IIPS / NPSB API client.
        """
        api_endpoint = getattr(settings, "BANGLADESH_BANK_API_URL", "")
        api_key      = getattr(settings, "BANGLADESH_BANK_API_KEY", "")

        if not api_endpoint:
            # Sandbox mode — log and return mock response
            logger.warning(
                f"BankTransfer SANDBOX [{rail}]: ref={reference} "
                f"receiver={receiver[:6]}*** amount={amount} fee={fee}"
            )
            return {
                "transaction_id":    txn_id,
                "rail":              rail,
                "amount":            str(amount),
                "fee":               str(fee),
                "net_amount":        str(amount - fee),
                "status":            "submitted",
                "reference":         reference,
                "estimated_arrival": cls._estimated_arrival(rail),
                "sandbox":           True,
            }

        # Production: POST to BB-IIPS gateway
        import requests
        payload = {
            "txn_id":       txn_id,
            "rail":         rail,
            "debit_amount": str(amount + fee),
            "credit_amount": str(amount),
            "fee":          str(fee),
            "receiver_account": receiver,
            "bank_code":    bank_code,
            "branch_code":  branch_code,
            "account_name": account_name,
            "reference":    reference,
            "currency":     "BDT",
        }
        resp = requests.post(
            f"{api_endpoint}/transfer",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=30,
        )
        if resp.status_code not in (200, 201, 202):
            raise GatewayError(
                f"BankTransfer [{rail}] HTTP {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json()
        return {
            "transaction_id":    data.get("txn_ref", txn_id),
            "rail":              rail,
            "amount":            str(amount),
            "fee":               str(fee),
            "net_amount":        str(amount - fee),
            "status":            data.get("status", "submitted"),
            "reference":         reference,
            "estimated_arrival": cls._estimated_arrival(rail),
        }
