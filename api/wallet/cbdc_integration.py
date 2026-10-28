# api/wallet/cbdc_integration.py
"""
CBDC (Central Bank Digital Currency) Integration.
Bangladesh: Digital Taka (expected 2026-2027, Bangladesh Bank Roadmap 2027).
Global: 90+ central banks piloting CBDCs by 2026.

Architecture:
  - Wallet can hold CBDC balance alongside BDT fiat balance
  - CBDC is a 6th balance type: cbdc_balance
  - Separate ledger entries for CBDC transactions
  - Interoperable with existing bKash/Nagad rails via BB IIPS

When Digital Taka goes live:
  1. Set BB_CBDC_API_KEY in settings
  2. Run: python manage.py migrate (adds cbdc_balance to Wallet)
  3. Enable feature flag: flags.set_global("cbdc_enabled", True)

Reference: Bangladesh Bank Smart Bangladesh Vision 2041
"""
import logging
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.cbdc")

CBDC_STATUS = {
    "BD": "PILOT_2027",       # Bangladesh Digital Taka — expected 2027
    "IN": "LIVE_2024",        # India e-Rupee — already live
    "CN": "LIVE_2020",        # China e-CNY — already live
    "EU": "PILOT_2027",       # Digital Euro — expected 2027
    "US": "RESEARCH",         # Digital Dollar — research phase
}


class CBDCService:
    """
    Central Bank Digital Currency service.
    Plugs into wallet system without modifying core code.
    Uses the existing plugin system: plugin_registry.register(CBDCPlugin())
    """

    API_URL = getattr(settings, "BB_CBDC_API_URL", "https://cbdc.bb.org.bd/api/v1")
    API_KEY = getattr(settings, "BB_CBDC_API_KEY", "")
    ENABLED = getattr(settings, "CBDC_ENABLED", False)

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if CBDC is enabled and configured."""
        from .feature_flags import flags
        return cls.ENABLED and bool(cls.API_KEY) and flags.is_enabled("cbdc_enabled")

    @classmethod
    def get_status(cls, country_code: str = "BD") -> dict:
        """Get CBDC status for a country."""
        status = CBDC_STATUS.get(country_code.upper(), "NOT_AVAILABLE")
        return {
            "country":       country_code,
            "status":        status,
            "is_live":       "LIVE" in status,
            "is_pilot":      "PILOT" in status,
            "is_configured": cls.is_enabled(),
            "note":          "Digital Taka expected 2027 (Bangladesh Bank Roadmap)",
        }

    @classmethod
    def credit_cbdc(cls, wallet, amount: Decimal, reference: str = "") -> dict:
        """
        Credit CBDC balance to wallet.
        Called when Bangladesh Bank transfers Digital Taka to user.
        """
        if not cls.is_enabled():
            return {"success": False, "error": "CBDC not yet active",
                    "note": "Expected: Bangladesh 2027"}
        try:
            import requests
            resp = requests.post(
                f"{cls.API_URL}/transfer/credit",
                json={
                    "wallet_id":  str(wallet.id),
                    "amount":     str(amount),
                    "currency":   "BDT-CBDC",
                    "reference":  reference,
                },
                headers={"Authorization": f"Bearer {cls.API_KEY}"},
                timeout=15,
            )
            data = resp.json()
            if data.get("status") == "SUCCESS":
                # Update wallet CBDC balance
                wallet.cbdc_balance = getattr(wallet, "cbdc_balance", Decimal("0")) + amount
                wallet.save(update_fields=["cbdc_balance", "updated_at"])
                logger.info(f"CBDC credited: wallet={wallet.id} amount={amount}")
                return {"success": True, "txn_id": data.get("txnId"), "amount": str(amount)}
            return {"success": False, "error": data.get("message", "CBDC credit failed")}
        except Exception as e:
            logger.error(f"CBDC credit error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def convert_cbdc_to_fiat(cls, wallet, amount: Decimal) -> dict:
        """
        Convert CBDC balance to regular BDT fiat.
        1 Digital Taka = 1 BDT (central bank guarantee).
        """
        if not cls.is_enabled():
            return {"success": False, "error": "CBDC not active"}
        cbdc_bal = getattr(wallet, "cbdc_balance", Decimal("0"))
        if cbdc_bal < amount:
            return {"success": False, "error": f"Insufficient CBDC balance: {cbdc_bal}"}
        try:
            from .services.core.WalletService import WalletService
            from django.db import transaction
            with transaction.atomic():
                wallet.cbdc_balance = cbdc_bal - amount
                wallet.save(update_fields=["cbdc_balance", "updated_at"])
                WalletService.credit(
                    wallet=wallet, amount=amount,
                    txn_type="cbdc_conversion",
                    description="CBDC → BDT conversion (1:1)",
                )
            return {"success": True, "converted": str(amount), "rate": "1:1"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def get_cbdc_balance(cls, wallet) -> Decimal:
        """Get wallet CBDC balance."""
        return getattr(wallet, "cbdc_balance", Decimal("0")) or Decimal("0")


class CBDCPlugin:
    """
    CBDC as a wallet plugin.
    Register in apps.py:
        from .cbdc_integration import CBDCPlugin
        from .plugins import plugin_registry
        plugin_registry.register(CBDCPlugin())
    """
    name = "cbdc"

    def on_wallet_created(self, wallet) -> None:
        """Initialize CBDC balance field for new wallets."""
        if not hasattr(wallet, "cbdc_balance"):
            return  # Field not yet in DB — run migrations first

    def validate_withdrawal(self, wallet, amount, method) -> str:
        """Block withdrawal if CBDC-only balance insufficient."""
        return None  # No block by default

    def on_credit(self, wallet, amount, txn) -> None:
        """Hook: notify user about CBDC credit."""
        if getattr(txn, "type", "") == "cbdc_conversion":
            logger.info(f"CBDC→fiat conversion: wallet={wallet.id} amount={amount}")
