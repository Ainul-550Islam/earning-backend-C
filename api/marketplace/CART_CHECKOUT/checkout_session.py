"""
CART_CHECKOUT/checkout_session.py — Checkout Session Management
================================================================
Multi-step checkout state stored in Redis/cache.
Prevents duplicate orders and handles payment timeouts.

Steps:
  1. cart_review   → Validate cart items, show totals
  2. address       → Collect/confirm shipping address
  3. payment       → Choose payment method
  4. review        → Final order review before confirm
  5. processing    → Payment in progress
  6. completed     → Order placed
"""
from __future__ import annotations
import uuid
import logging
from typing import Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

SESSION_TTL = 1800   # 30 minutes
CHECKOUT_STEPS = ["cart_review","address","payment","review","processing","completed"]


class CheckoutSession:
    """
    Stateful checkout session stored in cache.
    Each user gets one session at a time.
    """

    def __init__(self, session_id: str, data: dict):
        self.session_id = session_id
        self._data      = data

    # ── Properties ────────────────────────────────────────────────────────────
    @property
    def step(self) -> str:
        return self._data.get("step", "cart_review")

    @property
    def cart_id(self) -> Optional[int]:
        return self._data.get("cart_id")

    @property
    def user_id(self) -> Optional[int]:
        return self._data.get("user_id")

    @property
    def shipping_address(self) -> dict:
        return self._data.get("shipping_address", {})

    @property
    def payment_method(self) -> str:
        return self._data.get("payment_method", "cod")

    @property
    def coupon_code(self) -> str:
        return self._data.get("coupon_code", "")

    @property
    def totals(self) -> dict:
        return self._data.get("totals", {})

    @property
    def order_id(self) -> Optional[int]:
        return self._data.get("order_id")

    @property
    def is_expired(self) -> bool:
        expires_at = self._data.get("expires_at", 0)
        return timezone.now().timestamp() > expires_at

    # ── Mutations ─────────────────────────────────────────────────────────────
    def advance_step(self, next_step: str) -> "CheckoutSession":
        if next_step not in CHECKOUT_STEPS:
            raise ValueError(f"Invalid step: {next_step}")
        self._data["step"] = next_step
        self._save()
        return self

    def set_shipping_address(self, address: dict) -> "CheckoutSession":
        self._data["shipping_address"] = address
        self._save()
        return self

    def set_payment_method(self, method: str) -> "CheckoutSession":
        self._data["payment_method"] = method
        self._save()
        return self

    def set_coupon(self, code: str) -> "CheckoutSession":
        self._data["coupon_code"] = code
        self._save()
        return self

    def set_totals(self, totals: dict) -> "CheckoutSession":
        self._data["totals"] = totals
        self._save()
        return self

    def set_order_id(self, order_id: int) -> "CheckoutSession":
        self._data["order_id"] = order_id
        self._data["step"]     = "completed"
        self._save()
        return self

    def to_dict(self) -> dict:
        return {**self._data, "session_id": self.session_id}

    # ── Storage ───────────────────────────────────────────────────────────────
    def _save(self):
        self._data["updated_at"] = timezone.now().isoformat()
        cache.set(self._cache_key(), self._data, SESSION_TTL)

    def _cache_key(self) -> str:
        return f"checkout_session:{self.session_id}"

    def delete(self):
        cache.delete(self._cache_key())
        logger.debug("[Checkout] Session %s deleted", self.session_id)


# ── Factory functions ─────────────────────────────────────────────────────────

def create_checkout_session(user_id: int, cart_id: int, tenant_id: int) -> CheckoutSession:
    """Create a new checkout session for a user."""
    session_id = str(uuid.uuid4())
    now        = timezone.now()
    data = {
        "session_id":  session_id,
        "user_id":     user_id,
        "cart_id":     cart_id,
        "tenant_id":   tenant_id,
        "step":        "cart_review",
        "created_at":  now.isoformat(),
        "expires_at":  (now.timestamp() + SESSION_TTL),
        "shipping_address": {},
        "payment_method":   "cod",
        "coupon_code":      "",
        "totals":           {},
        "order_id":         None,
    }
    session = CheckoutSession(session_id, data)
    session._save()
    logger.info("[Checkout] Session created: %s (user=%s, cart=%s)", session_id, user_id, cart_id)
    return session


def get_checkout_session(session_id: str) -> Optional[CheckoutSession]:
    """Retrieve an existing checkout session."""
    key  = f"checkout_session:{session_id}"
    data = cache.get(key)
    if not data:
        return None
    session = CheckoutSession(session_id, data)
    if session.is_expired:
        session.delete()
        logger.warning("[Checkout] Session %s expired", session_id)
        return None
    return session


def get_user_active_session(user_id: int, tenant_id: int) -> Optional[CheckoutSession]:
    """Check if user already has an active checkout session."""
    key  = f"checkout_user_session:{tenant_id}:{user_id}"
    sid  = cache.get(key)
    if sid:
        return get_checkout_session(sid)
    return None


def extend_session(session: CheckoutSession) -> CheckoutSession:
    """Reset the TTL on a session."""
    session._data["expires_at"] = (timezone.now().timestamp() + SESSION_TTL)
    session._save()
    return session


def get_session_progress(session: CheckoutSession) -> dict:
    """Return step completion status."""
    current_idx = CHECKOUT_STEPS.index(session.step)
    return {
        "current_step":   session.step,
        "current_index":  current_idx,
        "total_steps":    len(CHECKOUT_STEPS),
        "percent":        int(current_idx / (len(CHECKOUT_STEPS) - 1) * 100),
        "steps":          [
            {
                "name":      s,
                "completed": i < current_idx,
                "current":   i == current_idx,
            }
            for i, s in enumerate(CHECKOUT_STEPS)
        ],
    }
