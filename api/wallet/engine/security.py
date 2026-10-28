# api/wallet/engine/security.py
"""
IntegrityShield — SHA-256 wallet tamper detection.

Every balance mutation:
  1. verify_hash(wallet)    → confirm stored hash matches recomputed hash
  2. <mutation happens>
  3. update_hash(wallet)    → store new SHA-256 hash of new state

Hash covers: wallet_id + user_id + current_balance + bonus_balance +
             total_earned + total_withdrawn + version

If a balance row is altered directly in DB (bypassing this engine),
verify_hash() will raise IntegrityError and block the mutation.
"""
import hashlib
import hmac
import logging
from decimal import Decimal

from django.conf import settings

from ..exceptions import SecurityLockError

logger = logging.getLogger("wallet.engine.security")

_SECRET = None


def _get_secret() -> bytes:
    """Lazy load HMAC secret from settings (falls back to a fixed dev key)."""
    global _SECRET
    if _SECRET is None:
        raw = getattr(settings, "WALLET_INTEGRITY_SECRET", "wallet-integrity-dev-secret-change-in-prod")
        _SECRET = raw.encode() if isinstance(raw, str) else raw
    return _SECRET


def _compute_hash(wallet) -> str:
    """
    Compute deterministic SHA-256 HMAC over wallet's financial fields.
    Uses HMAC (not plain SHA-256) so the hash is unforgeable without the secret.
    """
    payload = (
        f"{wallet.pk}"
        f":{wallet.user_id}"
        f":{wallet.current_balance}"
        f":{wallet.bonus_balance}"
        f":{wallet.total_earned}"
        f":{wallet.total_withdrawn}"
        f":{wallet.version}"
    ).encode()
    return hmac.new(_get_secret(), payload, hashlib.sha256).hexdigest()


def update_hash(wallet) -> str:
    """
    Compute and store the integrity hash on the wallet object.
    Call AFTER updating balance fields, BEFORE saving to DB.
    Returns the new hash string.
    """
    h = _compute_hash(wallet)
    wallet.integrity_hash = h
    return h


def verify_hash(wallet) -> None:
    """
    Verify the stored integrity_hash matches the recomputed hash.
    Raises SecurityLockError if tampered.
    Call BEFORE any balance mutation.
    """
    stored = getattr(wallet, "integrity_hash", None)

    # First-ever credit: no hash yet — generate and return
    if not stored:
        return

    expected = _compute_hash(wallet)
    if not hmac.compare_digest(stored, expected):
        logger.critical(
            f"INTEGRITY BREACH: wallet_id={wallet.pk} user_id={wallet.user_id} "
            f"stored={stored[:16]}… expected={expected[:16]}…"
        )
        # Lock wallet immediately to prevent further mutations
        try:
            wallet.is_locked = True
            wallet.locked_reason = "Integrity check failed — possible tamper"
            wallet.save(update_fields=["is_locked", "locked_reason"])
        except Exception:
            pass
        raise SecurityLockError(
            f"Wallet {wallet.pk} integrity check failed. Wallet has been locked."
        )

    logger.debug(f"Integrity OK: wallet_id={wallet.pk} hash={stored[:16]}…")
