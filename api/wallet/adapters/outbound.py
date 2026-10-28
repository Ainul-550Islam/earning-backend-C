# api/wallet/adapters/outbound.py
"""
Outbound Adapter — Wallet safely fetches data from other modules.

RULES:
  1. All calls wrapped in try/except — wallet works even if other module fails.
  2. Returns DTOs (contracts.py) or sensible defaults — never raises.
  3. Results are cached where safe (user level: 5min, risk score: 1min).
  4. No circular imports — uses lazy imports inside functions.

Modules we fetch from:
  - api.users        → UserLevel (tier multiplier, fee discount)
  - api.users        → UserStatistics (earning limits, streaks)
  - api.fraud_detection → UserRiskProfile (risk score, flags)
  - api.tasks        → TaskCompletion (task-based earnings)
  - api.tenants      → TenantMixin (tenant context for views)
  - api.admin_panel  → admin_site (for wallet admin registration)
"""
import logging
from decimal import Decimal
from typing import Optional, List

from django.core.cache import cache

from .contracts import (
    UserLevelInfo,
    UserRiskInfo,
    UserStatsInfo,
    TaskCompletionInfo,
)

logger = logging.getLogger("wallet.adapters.outbound")

# Cache TTLs
_LEVEL_CACHE_TTL = 300    # 5 minutes
_RISK_CACHE_TTL  = 60     # 1 minute (risk scores change faster)
_STATS_CACHE_TTL = 120    # 2 minutes


# ════════════════════════════════════════════════════════════════
# USERS MODULE
# ════════════════════════════════════════════════════════════════

def get_user_level_info(user_id: int) -> UserLevelInfo:
    """
    Fetch UserLevel from api.users to determine:
      - tier multiplier (task_reward_bonus)
      - withdrawal fee discount (withdrawal_fee_discount)
      - current level type (bronze/silver/gold/platinum/diamond)

    Returns sensible defaults if users module unavailable.
    Cached for 5 minutes.
    """
    cache_key = f"wallet_outbound_level:{user_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    result = UserLevelInfo(user_id=user_id, found=False)

    try:
        from api.users.models import UserLevel
        level = UserLevel.objects.filter(user_id=user_id).first()
        if level:
            result = UserLevelInfo(
                user_id=user_id,
                level_type=level.level_type or "bronze",
                current_level=level.current_level,
                task_reward_bonus=float(level.task_reward_bonus or 1.0),
                withdrawal_fee_discount=float(level.withdrawal_fee_discount or 0.0),
                experience_points=level.experience_points,
                found=True,
            )
    except Exception as e:
        logger.debug(f"get_user_level_info: users module unavailable user={user_id}: {e}")

    cache.set(cache_key, result, timeout=_LEVEL_CACHE_TTL)
    return result


def get_user_level_multiplier(user_id: int) -> Decimal:
    """
    Convenience: return just the earn multiplier for a user.
    Used by WalletService._apply_multipliers().
    Maps UserLevel.task_reward_bonus → Decimal multiplier.
    """
    info = get_user_level_info(user_id)
    return Decimal(str(info.task_reward_bonus))


def get_user_level_fee_discount(user_id: int) -> Decimal:
    """
    Convenience: return withdrawal fee discount percentage.
    Used by WithdrawalFeeService.
    """
    info = get_user_level_info(user_id)
    return Decimal(str(info.withdrawal_fee_discount))


def get_user_stats(user_id: int) -> UserStatsInfo:
    """
    Fetch UserStatistics from api.users.
    Used for daily earning cap checks and reporting sync.
    Cached 2 minutes.
    """
    cache_key = f"wallet_outbound_stats:{user_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    result = UserStatsInfo(user_id=user_id, found=False)

    try:
        from api.users.models import UserStatistics
        stats = UserStatistics.objects.filter(user_id=user_id).first()
        if stats:
            result = UserStatsInfo(
                user_id=user_id,
                total_tasks_completed=stats.total_tasks_completed or 0,
                tasks_completed_today=stats.tasks_completed_today or 0,
                daily_earning_limit_used=Decimal(str(stats.daily_earning_limit_used or 0)),
                current_streak=stats.current_streak or 0,
                total_earned=Decimal(str(stats.total_earned or 0)),
                found=True,
            )
    except Exception as e:
        logger.debug(f"get_user_stats: users module unavailable user={user_id}: {e}")

    cache.set(cache_key, result, timeout=_STATS_CACHE_TTL)
    return result


def get_user_kyc_level(user_id: int) -> int:
    """
    Fetch KYC verification level from api.users.
    Returns 0 (unverified) to 3 (fully verified).
    Used by WithdrawalLimitService for KYC-based limits.
    """
    try:
        from api.users.models import KYCVerification
        kyc = KYCVerification.objects.filter(user_id=user_id).first()
        if not kyc:
            return 0
        # Map KYC status to level int
        level_map = {
            "unverified": 0,
            "basic":      1,
            "verified":   2,
            "enhanced":   3,
        }
        return level_map.get(getattr(kyc, "status", "unverified"), 0)
    except Exception as e:
        logger.debug(f"get_user_kyc_level: users module unavailable user={user_id}: {e}")
        return 0


# ════════════════════════════════════════════════════════════════
# FRAUD DETECTION MODULE
# ════════════════════════════════════════════════════════════════

def get_user_risk_info(user_id: int) -> UserRiskInfo:
    """
    Fetch UserRiskProfile from api.fraud_detection.
    Used before large withdrawals and high-velocity credits.
    Cached 1 minute.
    """
    cache_key = f"wallet_outbound_risk:{user_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    result = UserRiskInfo(user_id=user_id, found=False)

    try:
        from api.fraud_detection.models import UserRiskProfile
        profile = UserRiskProfile.objects.filter(user_id=user_id).first()
        if profile:
            result = UserRiskInfo(
                user_id=user_id,
                overall_risk_score=profile.overall_risk_score or 0,
                is_flagged=profile.is_flagged,
                is_restricted=profile.is_restricted,
                monitoring_level=profile.monitoring_level or "normal",
                payment_risk_score=profile.payment_risk_score or 0,
                found=True,
            )
    except Exception as e:
        logger.debug(f"get_user_risk_info: fraud_detection unavailable user={user_id}: {e}")

    cache.set(cache_key, result, timeout=_RISK_CACHE_TTL)
    return result


def is_user_high_risk(user_id: int, threshold: int = 70) -> bool:
    """
    Quick check: is user's risk score above threshold?
    Used by WithdrawalService before large payouts.
    """
    risk = get_user_risk_info(user_id)
    return risk.found and (risk.overall_risk_score >= threshold or risk.is_restricted)


def report_suspicious_activity(user_id: int, activity_type: str, detail: str = "") -> None:
    """
    Push a suspicious wallet activity event to fraud_detection.
    Best-effort — never blocks wallet operations.
    Called by: WalletManager velocity check, large withdrawal flag.
    """
    try:
        from api.fraud_detection.services import FraudService
        FraudService.record_event(
            user_id=user_id,
            event_type=activity_type,
            source="wallet",
            detail=detail,
        )
        # Invalidate cached risk score
        cache.delete(f"wallet_outbound_risk:{user_id}")
    except Exception as e:
        logger.debug(f"report_suspicious_activity: fraud_detection unavailable: {e}")


# ════════════════════════════════════════════════════════════════
# TASKS MODULE
# ════════════════════════════════════════════════════════════════

def get_task_completions(user_id: int, limit: int = 50) -> List[TaskCompletionInfo]:
    """
    Fetch recent task completions from api.tasks.
    Used by data_bridge.py for wallet-task sync.
    """
    try:
        from api.tasks.models import Task, TaskCompletion
        completions = TaskCompletion.objects.filter(
            user_id=user_id, status="approved"
        ).select_related("task").order_by("-created_at")[:limit]

        return [
            TaskCompletionInfo(
                task_id=str(tc.task_id),
                user_id=user_id,
                amount=Decimal(str(tc.reward_amount if hasattr(tc, "reward_amount") else 0)),
                completed_at=tc.created_at if hasattr(tc, "created_at") else None,
                status="approved",
            )
            for tc in completions
        ]
    except Exception as e:
        logger.debug(f"get_task_completions: tasks module unavailable user={user_id}: {e}")
        return []


# ════════════════════════════════════════════════════════════════
# TENANT / ADMIN MODULES
# ════════════════════════════════════════════════════════════════

def get_tenant_mixin():
    """
    Fetch TenantMixin from api.tenants for wallet views.
    Returns a no-op mixin if tenants module unavailable.
    """
    try:
        from api.tenants.mixins import TenantMixin
        return TenantMixin
    except Exception:
        logger.debug("TenantMixin unavailable — using no-op mixin")

        class NoOpTenantMixin:
            pass

        return NoOpTenantMixin


def get_admin_site():
    """
    Fetch custom admin_site from api.admin_panel.
    Falls back to django.contrib.admin.site if unavailable.
    """
    try:
        from api.admin_panel.admin import admin_site as modern_site
        return modern_site
    except Exception:
        logger.debug("admin_panel.admin_site unavailable — using default Django admin")
        from django.contrib import admin
        return admin.site


def invalidate_user_cache(user_id: int) -> None:
    """
    Clear all outbound caches for a user.
    Call after wallet mutations that affect multipliers.
    """
    for prefix in ["wallet_outbound_level", "wallet_outbound_stats", "wallet_outbound_risk"]:
        cache.delete(f"{prefix}:{user_id}")
