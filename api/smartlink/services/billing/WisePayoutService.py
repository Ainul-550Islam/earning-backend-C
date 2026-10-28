"""
SmartLink — Wise (TransferWise) Transfers API Service
======================================================
Self-contained Wise integration. No imports from any other api.* app.
Uses Wise API v3 (Transfers).

Required Django settings:
    SMARTLINK_WISE_API_KEY      = "..."    # Wise API token
    SMARTLINK_WISE_PROFILE_ID   = 12345    # Wise Business/Personal profile ID
    SMARTLINK_WISE_MODE         = "sandbox" | "live"  (default: "sandbox")

Wise payout flow:
  1. Create a quote   (source amount + currency pair)
  2. Create a recipient account (target publisher's bank details)
  3. Create a transfer (quote + recipient)
  4. Fund the transfer (debit your Wise balance)
"""
import logging
import uuid
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("smartlink.billing.wise")

_BASE = {
    "sandbox": "https://api.sandbox.transferwise.tech",
    "live":    "https://api.wise.com",
}


class WisePayoutService:
    """
    Sends payouts via Wise Transfers API.

    Usage:
        svc = WisePayoutService()
        result = svc.send_payout(payout_record)
        # result → {"success": True, "transfer_id": 123, "transaction_id": "123"}
    """

    def __init__(self):
        mode = getattr(settings, "SMARTLINK_WISE_MODE", "sandbox")
        self.base_url   = _BASE.get(mode, _BASE["sandbox"])
        self.api_key    = getattr(settings, "SMARTLINK_WISE_API_KEY", "")
        self.profile_id = getattr(settings, "SMARTLINK_WISE_PROFILE_ID", None)

    # ── Auth headers ──────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

    # ── Step 1: Create Quote ──────────────────────────────────────────────────

    def _create_quote(self, amount: Decimal, source_currency: str, target_currency: str) -> int:
        """
        Create a Wise quote and return the quoteUuid.
        Wise needs a quote to fix the FX rate before transfer.
        """
        payload = {
            "profile":         self.profile_id,
            "sourceCurrency":  source_currency,
            "targetCurrency":  target_currency,
            "targetAmount":    float(amount),
            "payOut":          "BANK_TRANSFER",
        }
        resp = requests.post(
            f"{self.base_url}/v3/profiles/{self.profile_id}/quotes",
            json=payload,
            headers=self._headers(),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        quote_id = data.get("id") or data.get("quoteUuid")
        if not quote_id:
            raise ValueError(f"Wise quote missing id: {data}")
        logger.debug(f"Wise quote created: id={quote_id}")
        return quote_id

    # ── Step 2: Create / Retrieve Recipient Account ───────────────────────────

    def _get_or_create_recipient(self, payout_record) -> int:
        """
        Create a Wise recipient account for the publisher.
        In a full implementation, you'd cache the accountId to avoid duplicates.
        For simplicity, we create a new one per transfer (Wise deduplicates by IBAN/email).
        """
        # Email recipient (PayPal-style — for Wise Payouts product, not Transfers)
        # For bank wire we'd need IBAN / routing details.
        # Here we handle EMAIL recipients (for Wise Balance payouts) as the common case.
        payload = {
            "profile":     self.profile_id,
            "accountHolderName": payout_record.publisher.get_full_name() or payout_record.publisher.username,
            "currency":    payout_record.currency or "USD",
            "type":        "email",
            "details": {
                "email": payout_record.payment_address,
            },
        }
        resp = requests.post(
            f"{self.base_url}/v1/accounts",
            json=payload,
            headers=self._headers(),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        account_id = data.get("id")
        if not account_id:
            raise ValueError(f"Wise recipient account missing id: {data}")
        logger.debug(f"Wise recipient created: accountId={account_id}")
        return account_id

    # ── Step 3: Create Transfer ───────────────────────────────────────────────

    def _create_transfer(self, quote_id, recipient_id: int, reference_id: str) -> dict:
        """Create a Wise transfer linking the quote and recipient."""
        payload = {
            "targetAccount":      recipient_id,
            "quoteUuid":          quote_id,
            "customerTransactionId": reference_id,
            "details": {
                "reference": f"SmartLink payout {reference_id}",
            },
        }
        resp = requests.post(
            f"{self.base_url}/v1/transfers",
            json=payload,
            headers=self._headers(),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        transfer_id = data.get("id")
        if not transfer_id:
            raise ValueError(f"Wise transfer missing id: {data}")
        logger.debug(f"Wise transfer created: transferId={transfer_id}")
        return data

    # ── Step 4: Fund Transfer ─────────────────────────────────────────────────

    def _fund_transfer(self, transfer_id: int) -> dict:
        """
        Fund (execute) the transfer from Wise balance.
        Wise will deduct from the profile's balance in the source currency.
        """
        resp = requests.post(
            f"{self.base_url}/v3/profiles/{self.profile_id}/transfers/{transfer_id}/payments",
            json={"type": "BALANCE"},
            headers=self._headers(),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.debug(f"Wise transfer funded: transferId={transfer_id} status={data.get('status')}")
        return data

    # ── Public: send_payout ───────────────────────────────────────────────────

    def send_payout(self, payout_record) -> dict:
        """
        Execute full Wise payout flow for a PayoutRecord.

        Args:
            payout_record: smartlink.models.billing.PayoutRecord instance

        Returns:
            {
                "success":        bool,
                "transfer_id":    int | 0,
                "transaction_id": str,
                "status":         str,
                "error":          str | "",
            }
        """
        if not self.api_key or not self.profile_id:
            return self._error(
                "Wise credentials not configured "
                "(SMARTLINK_WISE_API_KEY / SMARTLINK_WISE_PROFILE_ID)"
            )

        amount          = payout_record.net_amount.quantize(Decimal("0.01"))
        currency        = payout_record.currency or "USD"
        reference_id    = str(payout_record.reference_id)

        try:
            # Step 1 — Quote
            quote_id = self._create_quote(
                amount=amount,
                source_currency="USD",   # Wise balance is always funded in USD
                target_currency=currency,
            )

            # Step 2 — Recipient
            recipient_id = self._get_or_create_recipient(payout_record)

            # Step 3 — Transfer
            transfer_data = self._create_transfer(quote_id, recipient_id, reference_id)
            transfer_id   = transfer_data["id"]

            # Step 4 — Fund
            fund_data = self._fund_transfer(transfer_id)
            status    = fund_data.get("status", "processing")

            logger.info(
                f"Wise payout sent: ref={reference_id} "
                f"transfer_id={transfer_id} amount={amount} {currency} status={status}"
            )
            return {
                "success":        True,
                "transfer_id":    transfer_id,
                "transaction_id": str(transfer_id),
                "status":         status.upper(),
                "error":          "",
            }

        except requests.exceptions.HTTPError as e:
            body = ""
            try:
                body = e.response.json()
            except Exception:
                body = e.response.text if e.response else ""
            msg = f"Wise HTTP {e.response.status_code}: {body}"
            logger.error(f"Wise payout failed: ref={reference_id} — {msg}")
            return self._error(msg)

        except requests.exceptions.Timeout:
            return self._error("Wise API timeout")

        except requests.exceptions.ConnectionError as e:
            return self._error(f"Wise connection error: {e}")

        except Exception as e:
            logger.exception(f"Wise unexpected error for ref={reference_id}")
            return self._error(str(e))

    # ── Status check ──────────────────────────────────────────────────────────

    def get_transfer_status(self, transfer_id: int) -> dict:
        """Poll Wise for transfer status. Returns raw Wise transfer dict."""
        if not self.api_key:
            return {"error": "Wise API key not configured"}
        try:
            resp = requests.get(
                f"{self.base_url}/v1/transfers/{transfer_id}",
                headers=self._headers(),
                timeout=15,
            )
            data = resp.json()
            if resp.status_code == 200:
                return {
                    "transfer_id": data.get("id"),
                    "status":      data.get("status", "UNKNOWN").upper(),
                    "error":       "",
                }
            return {"error": data.get("errors", [{}])[0].get("message", "Unknown")}
        except Exception as e:
            return {"error": str(e)}

    # ── Helper ────────────────────────────────────────────────────────────────

    @staticmethod
    def _error(message: str) -> dict:
        return {
            "success":        False,
            "transfer_id":    0,
            "transaction_id": "",
            "status":         "FAILED",
            "error":          message,
        }
