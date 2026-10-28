# api/wallet/open_banking.py
"""
Open Banking API Integration.
2026 trend: Open Banking expanding globally.
Bangladesh: Bangladesh Bank moving toward open banking standards.
EU: PSD2 already live. India: Account Aggregator framework.

Features:
  - Link bank account to wallet (read-only access)
  - Import bank transaction history
  - Direct bank-to-wallet top-up (instant)
  - Balance aggregation across accounts
  - Spending analysis from bank data

Architecture: Uses OAuth2 + bank APIs (Plaid/TrueLayer/local BB API).
Plugin-based: no core code modified.
"""
import logging
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.open_banking")


class OpenBankingService:
    """Open banking account aggregation and data import."""

    PROVIDER    = getattr(settings, "OPEN_BANKING_PROVIDER", "truelayer")
    CLIENT_ID   = getattr(settings, "OPEN_BANKING_CLIENT_ID", "")
    CLIENT_SECRET = getattr(settings, "OPEN_BANKING_CLIENT_SECRET", "")
    ENABLED     = getattr(settings, "OPEN_BANKING_ENABLED", False)

    # Supported banks (Bangladesh + international)
    SUPPORTED_BANKS = {
        "BD": ["Dutch Bangla Bank", "BRAC Bank", "Eastern Bank",
               "Mutual Trust Bank", "City Bank", "Prime Bank"],
        "IN": ["HDFC", "ICICI", "SBI", "Axis"],  # via Account Aggregator
        "EU": ["Any PSD2-compliant bank"],
        "UK": ["Any FCA-regulated bank"],
    }

    @classmethod
    def get_auth_url(cls, user_id: int, redirect_uri: str) -> dict:
        """
        Get OAuth2 authorization URL for bank linking.
        User visits this URL → grants read access → redirected back.
        """
        if not cls.ENABLED:
            return {
                "success": False,
                "error":   "Open Banking not enabled",
                "note":    "Set OPEN_BANKING_ENABLED=True and configure provider",
                "provider":cls.PROVIDER,
            }
        try:
            state = f"user_{user_id}_{__import__('uuid').uuid4().hex[:8]}"
            if cls.PROVIDER == "truelayer":
                url = (
                    f"https://auth.truelayer.com/?response_type=code"
                    f"&client_id={cls.CLIENT_ID}"
                    f"&scope=accounts balance transactions"
                    f"&redirect_uri={redirect_uri}"
                    f"&state={state}"
                    f"&providers=uk-ob-all uk-oauth-all"
                )
            elif cls.PROVIDER == "plaid":
                url = f"https://cdn.plaid.com/link/v2/stable/link.html?token=..."
            else:
                url = ""

            from django.core.cache import cache
            cache.set(f"ob_state:{state}", {"user_id": user_id}, 600)
            return {"success": True, "auth_url": url, "state": state}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def exchange_token(cls, code: str, state: str) -> dict:
        """Exchange authorization code for access token after OAuth callback."""
        try:
            import requests
            from django.core.cache import cache
            state_data = cache.get(f"ob_state:{state}")
            if not state_data:
                return {"success": False, "error": "Invalid or expired state"}

            resp = requests.post(
                "https://auth.truelayer.com/connect/token",
                data={
                    "grant_type":    "authorization_code",
                    "client_id":     cls.CLIENT_ID,
                    "client_secret": cls.CLIENT_SECRET,
                    "code":          code,
                    "redirect_uri":  getattr(settings, "OPEN_BANKING_REDIRECT_URI", ""),
                },
                timeout=30,
            )
            data = resp.json()
            if "access_token" in data:
                user_id    = state_data["user_id"]
                token      = data["access_token"]
                cache.set(f"ob_token:user_{user_id}", token, data.get("expires_in", 3600))
                return {"success": True, "user_id": user_id, "token_stored": True}
            return {"success": False, "error": data.get("error", "Token exchange failed")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def get_accounts(cls, user_id: int) -> list:
        """Get list of linked bank accounts for user."""
        try:
            from django.core.cache import cache
            import requests
            token = cache.get(f"ob_token:user_{user_id}")
            if not token:
                return []
            resp = requests.get(
                "https://api.truelayer.com/data/v1/accounts",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            data = resp.json()
            return data.get("results", [])
        except Exception as e:
            logger.error(f"Open banking accounts error: {e}")
            return []

    @classmethod
    def import_transactions(cls, user_id: int, account_id: str,
                             days: int = 90) -> dict:
        """
        Import bank transaction history into wallet analytics.
        Does NOT credit wallet — read-only data import for insights.
        """
        try:
            from django.core.cache import cache
            import requests
            from datetime import datetime, timedelta
            token = cache.get(f"ob_token:user_{user_id}")
            if not token:
                return {"success": False, "error": "No bank token — please re-link account"}
            from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            resp = requests.get(
                f"https://api.truelayer.com/data/v1/accounts/{account_id}/transactions",
                headers={"Authorization": f"Bearer {token}"},
                params={"from": from_date},
                timeout=20,
            )
            data = resp.json()
            txns = data.get("results", [])
            total_in  = sum(t["amount"] for t in txns if t.get("amount", 0) > 0)
            total_out = sum(abs(t["amount"]) for t in txns if t.get("amount", 0) < 0)
            logger.info(f"Imported {len(txns)} bank txns for user={user_id}")
            return {
                "success":       True,
                "imported":      len(txns),
                "total_credits": round(total_in, 2),
                "total_debits":  round(total_out, 2),
                "period_days":   days,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def direct_topup(cls, user_id: int, account_id: str, amount: Decimal) -> dict:
        """
        Initiate direct bank-to-wallet transfer (requires PSD2/open banking rails).
        Creates payment initiation request to bank.
        """
        return {
            "success": False,
            "error":   "Direct bank top-up requires PSD2 payment initiation",
            "note":    "Available in EU/UK markets. Bangladesh: use bKash/Nagad.",
            "alternative": "Use bKash/Nagad/Rocket for instant Bangladesh top-up",
        }
