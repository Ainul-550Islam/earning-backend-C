# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Signal Connector
signals/connector.py

PURPOSE:
    This file was MISSING. All 7 signal handler files had connect_*_signals()
    functions defined but they were NEVER CALLED — making every handler
    "floating" (written but not wired).

    This file calls all connect_*_signals() during Django startup via
    apps.py → ready() → import signals.connector

FIX APPLIED:
    Each connect_*_signals() call is wrapped individually so a missing
    business model (e.g. payment_gateways not installed) silently skips that
    domain instead of crashing the entire webhook system.

BUG FIX (this audit): every connect_*_signals() function below imported its
business model from a nonexistent `apps.X` namespace (e.g.
`apps.payments.models.Payment`). This project has no `apps.` package —
sibling apps live directly under `api.` with their own names. All 7 signal
files caught ImportError, so nothing crashed, but 6 of 7 domains silently
never connected in production. Corrected below; wallet, fraud, kyc, and
payment map to a single unambiguous app directory. offer and withdrawal had
no single unambiguous match without the sibling app source, so those two
now try a short list of the most likely candidate apps in order (see
_resolve_offer_model() in offer_signals.py and
_resolve_withdrawal_request_model() in withdrawal_signals.py) — confirm
against the real model locations and trim the list once verified.

WIRING MAP (what fires what):
    api.payment_gateways.models.Payment                 → payment_signals    (6 handlers)
    api.fraud_detection.models.FraudDetection           → fraud_signals      (5 handlers)
    api.kyc.models.KYCApplication                       → kyc_signals        (6 handlers)
    api.offer_inventory|offer_routing.models.Offer      → offer_signals      (5 handlers)  [best-effort, verify]
    django.contrib.auth.models.User (get_user_model())  → user_signals       (6 handlers)
    api.wallet.models.WalletTransaction                 → wallet_signals     (4 handlers)
    api.wallet|payout_queue.models.WithdrawalRequest    → withdrawal_signals (5 handlers)  [best-effort, verify]
"""

import logging

logger = logging.getLogger("ainul.webhooks.signals")


def _try_connect(connect_fn, domain: str) -> bool:
    """
    Safely call a connect_*_signals() function.

    Returns True on success, False when the business app is not installed.
    Any unexpected error is re-raised so misconfiguration is visible.
    """
    try:
        connect_fn()
        logger.debug("[Webhooks] ✓ %s signals connected", domain)
        return True
    except ImportError:
        logger.info(
            "[Webhooks] ⚠ %s app not installed — skipping signal wiring. "
            "Install the app or remove its entry from connector.py.",
            domain,
        )
        return False
    except Exception:
        logger.exception("[Webhooks] ✗ Unexpected error connecting %s signals", domain)
        raise


def connect_all_signals() -> dict:
    """
    Connect every business-domain signal handler to its Django model signals.

    Called once from WebhooksConfig.ready() via:
        import api.webhooks.signals.connector

    Returns a dict of {domain: connected_bool} for diagnostics.
    """
    results = {}

    # ── Payment signals ───────────────────────────────────────────────────────
    from .payment_signals import connect_payment_signals
    results["payment"] = _try_connect(connect_payment_signals, "payment")

    # ── Fraud signals ─────────────────────────────────────────────────────────
    from .fraud_signals import connect_fraud_signals
    results["fraud"] = _try_connect(connect_fraud_signals, "fraud")

    # ── KYC signals ───────────────────────────────────────────────────────────
    from .kyc_signals import connect_kyc_signals
    results["kyc"] = _try_connect(connect_kyc_signals, "kyc")

    # ── Offer signals ─────────────────────────────────────────────────────────
    from .offer_signals import connect_offer_signals
    results["offer"] = _try_connect(connect_offer_signals, "offer")

    # ── User signals ──────────────────────────────────────────────────────────
    from .user_signals import connect_user_signals
    results["user"] = _try_connect(connect_user_signals, "user")

    # ── Wallet / WalletTransaction signals ────────────────────────────────────
    from .wallet_signals import connect_wallet_signals
    results["wallet"] = _try_connect(connect_wallet_signals, "wallet")

    # ── Withdrawal signals ────────────────────────────────────────────────────
    from .withdrawal_signals import connect_withdrawal_signals
    results["withdrawal"] = _try_connect(connect_withdrawal_signals, "withdrawal")

    connected   = sum(1 for v in results.values() if v)
    total       = len(results)
    logger.info(
        "[Webhooks] Signal connector: %d/%d domains wired successfully — %s",
        connected, total, results,
    )
    return results


# ── Auto-connect when this module is imported ─────────────────────────────────
# apps.py calls: import api.webhooks.signals.connector
# That import triggers module-level code → connect_all_signals() runs once.
connect_all_signals()
