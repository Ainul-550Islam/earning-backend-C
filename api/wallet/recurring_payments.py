# api/wallet/recurring_payments.py
"""
Recurring Payments — subscription and scheduled payment management.

Features:
  - Create recurring payment plan (daily/weekly/monthly/quarterly/yearly)
  - Auto-deduct from wallet at schedule
  - Skip/pause/cancel anytime
  - Retry on failure (3 attempts)
  - Notification before each deduction

Integration: Uses Celery Beat (already in celery_beat_config.py).
No core code modified — pure extension via event_bus + hooks.

Cache backend notes
───────────────────
The original implementation called ``cache.client.get_client()`` (a
django-redis / django-valkey private API) for key scanning.  That call
raises ``AttributeError`` on every other cache backend (LocMemCache,
DatabaseCache, FileBasedCache, pymemcache, …) and also in test runs
that use the dummy cache.

This revision adds a **two-tier scan strategy**:

  1. Try the redis/valkey native ``SCAN`` via ``cache.client.get_client()``
     (unchanged behaviour when redis-backed).
  2. Fall back to a Django-native index: a set stored under the key
     ``recurring:__index__`` that tracks all live plan IDs.  Every
     ``create``, ``pause``, ``cancel`` operation keeps the index current.
     ``execute_due_payments`` uses the index when the native scan is
     unavailable.

The index approach works with *any* Django cache backend that supports
``get`` / ``set``, which means unit tests using ``CACHES = {"default":
{"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}`` now
work correctly without mocking Redis internals.
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger("wallet.recurring")

FREQUENCIES = {
    "daily":     {"days": 1,   "name": "Daily"},
    "weekly":    {"days": 7,   "name": "Weekly"},
    "monthly":   {"days": 30,  "name": "Monthly"},
    "quarterly": {"days": 90,  "name": "Quarterly"},
    "yearly":    {"days": 365, "name": "Yearly"},
}

# How long plans survive without being touched (400 days)
_PLAN_TTL = 86400 * 400
# Index key that holds the set of all known plan_ids
_INDEX_KEY = "recurring:__index__"


# ─────────────────────────────────────────────────────────────────────────────
# Internal index helpers (Django-cache-native fallback for Redis SCAN)
# ─────────────────────────────────────────────────────────────────────────────

def _index_add(plan_id: str) -> None:
    """Register plan_id in the portable index."""
    try:
        index: set = cache.get(_INDEX_KEY) or set()
        index.add(plan_id)
        cache.set(_INDEX_KEY, index, _PLAN_TTL)
    except Exception as exc:
        logger.debug(f"recurring index add failed: {exc}")


def _index_remove(plan_id: str) -> None:
    """Remove plan_id from the portable index (best-effort)."""
    try:
        index: set = cache.get(_INDEX_KEY) or set()
        index.discard(plan_id)
        cache.set(_INDEX_KEY, index, _PLAN_TTL)
    except Exception as exc:
        logger.debug(f"recurring index remove failed: {exc}")


def _scan_plan_ids() -> list[str]:
    """
    Return all plan IDs using the fastest available method:
      1. Redis/Valkey native SCAN (zero overhead, works at scale).
      2. Portable Django-cache index (any backend, test-safe).
    """
    # ── Strategy 1: Redis native SCAN ────────────────────────────────
    try:
        client = cache.client.get_client()          # django-redis / django-valkey
        raw_keys = list(client.scan_iter("recurring:*", count=500))
        plan_ids = []
        for key in raw_keys:
            decoded = key.decode() if isinstance(key, bytes) else key
            # Skip the index key itself
            if decoded == _INDEX_KEY:
                continue
            # key format is  "recurring:<plan_id>"
            parts = decoded.split(":", 1)
            if len(parts) == 2 and parts[1]:
                plan_ids.append(parts[1])
        return plan_ids
    except AttributeError:
        pass  # cache backend has no .client  →  fall through
    except Exception as exc:
        logger.debug(f"Redis SCAN failed, falling back to index: {exc}")

    # ── Strategy 2: Portable index ───────────────────────────────────
    try:
        index: set = cache.get(_INDEX_KEY) or set()
        return list(index)
    except Exception as exc:
        logger.warning(f"recurring _scan_plan_ids index read failed: {exc}")
        return []


class RecurringPaymentService:
    """Manage recurring/subscription payments from wallet."""

    @staticmethod
    def create(
        user, wallet, amount: Decimal, frequency: str,
        beneficiary: str, description: str = "",
        start_date=None, end_date=None,
        max_payments: int = None,
    ) -> dict:
        """
        Create a recurring payment plan.

        Args:
            frequency:    daily/weekly/monthly/quarterly/yearly
            beneficiary:  wallet username or account to pay
            max_payments: None = infinite, or specific count
        """
        if frequency not in FREQUENCIES:
            return {"success": False,
                    "error": f"Invalid frequency. Choose: {list(FREQUENCIES.keys())}"}
        if amount <= 0:
            return {"success": False, "error": "Amount must be positive"}
        if amount > wallet.available_balance and not max_payments:
            return {"success": False, "error": "Insufficient balance for recurring payment"}

        import uuid
        from datetime import timedelta

        plan_id   = uuid.uuid4().hex[:12]
        freq_cfg  = FREQUENCIES[frequency]
        next_run  = start_date or (timezone.now() + timedelta(days=1)).date()

        plan = {
            "plan_id":       plan_id,
            "user_id":       user.id,
            "wallet_id":     wallet.id,
            "amount":        str(amount),
            "frequency":     frequency,
            "beneficiary":   beneficiary,
            "description":   description[:200],
            "status":        "active",
            "payments_made": 0,
            "max_payments":  max_payments,
            "next_run":      str(next_run),
            "end_date":      str(end_date) if end_date else None,
            "created_at":    timezone.now().isoformat(),
            "last_run":      None,
            "failures":      0,
        }

        cache.set(f"recurring:{plan_id}", plan, _PLAN_TTL)
        _index_add(plan_id)

        logger.info(
            f"Recurring payment created: {plan_id} "
            f"user={user.id} freq={frequency} amount={amount}"
        )
        return {
            "success":     True,
            "plan_id":     plan_id,
            "amount":      str(amount),
            "frequency":   freq_cfg["name"],
            "next_run":    str(next_run),
            "beneficiary": beneficiary,
        }

    @staticmethod
    def execute_due_payments() -> dict:
        """
        Execute all due recurring payments.
        Called by: tasks/recurring_payment_tasks.py (Celery Beat daily).
        """
        from datetime import date

        today     = str(date.today())
        executed  = failed = skipped = 0

        plan_ids = _scan_plan_ids()
        if not plan_ids and not isinstance(plan_ids, list):
            return {"error": "Cache scan failed"}

        for plan_id in plan_ids:
            plan = cache.get(f"recurring:{plan_id}")
            if not plan or plan.get("status") != "active":
                continue
            if plan.get("next_run", "9999") > today:
                continue

            result = RecurringPaymentService._execute_payment(plan)
            if result["success"]:
                executed += 1
            elif result.get("fatal"):
                failed += 1
            else:
                skipped += 1

        return {"executed": executed, "failed": failed, "skipped": skipped}

    @staticmethod
    def _execute_payment(plan: dict) -> dict:
        """Execute a single recurring payment."""
        from datetime import timedelta, date

        plan_id = plan["plan_id"]
        try:
            from django.contrib.auth import get_user_model
            from .services.core.WalletService import WalletService

            User   = get_user_model()
            user   = User.objects.get(id=plan["user_id"])
            result = WalletService.get_or_create(user)
            wallet = result[0] if isinstance(result, tuple) else result

            amount = Decimal(plan["amount"])
            if wallet.available_balance < amount:
                plan["failures"] = plan.get("failures", 0) + 1
                if plan["failures"] >= 3:
                    plan["status"] = "failed"
                    logger.warning(f"Recurring payment failed 3×: {plan_id}")
                    _index_remove(plan_id)
                plan["next_run"] = str(date.today() + timedelta(days=1))
                cache.set(f"recurring:{plan_id}", plan, _PLAN_TTL)
                return {"success": False, "error": "Insufficient balance"}

            WalletService.debit(
                wallet=wallet,
                amount=amount,
                txn_type="recurring_payment",
                description=(
                    f"Recurring: {plan.get('description', '')} "
                    f"→ {plan['beneficiary']}"
                ),
            )

            plan["payments_made"] = plan.get("payments_made", 0) + 1
            plan["last_run"]      = str(date.today())
            plan["failures"]      = 0

            freq_days     = FREQUENCIES[plan["frequency"]]["days"]
            plan["next_run"] = str(date.today() + timedelta(days=freq_days))

            max_p = plan.get("max_payments")
            if max_p and plan["payments_made"] >= max_p:
                plan["status"] = "completed"
                _index_remove(plan_id)
                logger.info(f"Recurring plan completed: {plan_id}")

            end_d = plan.get("end_date")
            if end_d and plan["next_run"] > end_d:
                plan["status"] = "completed"
                _index_remove(plan_id)

            cache.set(f"recurring:{plan_id}", plan, _PLAN_TTL)
            logger.info(f"Recurring payment executed: {plan_id} amount={amount}")
            return {"success": True, "amount": str(amount)}

        except Exception as exc:
            logger.error(f"Recurring payment error: {plan_id}: {exc}")
            return {"success": False, "error": str(exc), "fatal": True}

    @staticmethod
    def pause(plan_id: str, user_id: int) -> dict:
        """Pause a recurring payment plan."""
        plan = cache.get(f"recurring:{plan_id}")
        if not plan or plan.get("user_id") != user_id:
            return {"success": False, "error": "Plan not found"}
        plan["status"] = "paused"
        cache.set(f"recurring:{plan_id}", plan, _PLAN_TTL)
        return {"success": True, "status": "paused"}

    @staticmethod
    def resume(plan_id: str, user_id: int) -> dict:
        """Resume a paused recurring payment plan."""
        plan = cache.get(f"recurring:{plan_id}")
        if not plan or plan.get("user_id") != user_id:
            return {"success": False, "error": "Plan not found"}
        if plan.get("status") != "paused":
            return {"success": False, "error": "Plan is not paused"}
        plan["status"] = "active"
        cache.set(f"recurring:{plan_id}", plan, _PLAN_TTL)
        return {"success": True, "status": "active"}

    @staticmethod
    def cancel(plan_id: str, user_id: int) -> dict:
        """Cancel a recurring payment plan."""
        plan = cache.get(f"recurring:{plan_id}")
        if not plan or plan.get("user_id") != user_id:
            return {"success": False, "error": "Plan not found"}
        plan["status"] = "cancelled"
        cache.set(f"recurring:{plan_id}", plan, _PLAN_TTL)
        _index_remove(plan_id)
        return {"success": True, "status": "cancelled"}

    @staticmethod
    def get(plan_id: str, user_id: int) -> dict | None:
        """Fetch a single plan (user-scoped)."""
        plan = cache.get(f"recurring:{plan_id}")
        if plan and plan.get("user_id") == user_id:
            return plan
        return None

    @staticmethod
    def list_for_user(user_id: int) -> list:
        """List all recurring plans for a user."""
        plan_ids = _scan_plan_ids()
        plans = []
        for plan_id in plan_ids:
            p = cache.get(f"recurring:{plan_id}")
            if p and p.get("user_id") == user_id:
                plans.append(p)
        return plans
