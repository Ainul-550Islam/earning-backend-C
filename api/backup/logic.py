"""
Backup Module Core Business Logic
Pure functions and logic helpers that contain no Django ORM calls.
Designed to be easily testable in isolation.
"""

import math
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from croniter import croniter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retention Logic
# ---------------------------------------------------------------------------

def should_retain_backup(created_at: datetime, retention_days: int, now: Optional[datetime] = None) -> bool:
    """Return True if backup should still be kept (not yet expired)"""
    now = now or datetime.utcnow()
    expiry = created_at + timedelta(days=retention_days)
    return now < expiry


def calculate_expiry_date(created_at: datetime, retention_days: int) -> datetime:
    """Calculate when a backup expires"""
    return created_at + timedelta(days=retention_days)


def filter_expired_backups(backups: List[Dict], now: Optional[datetime] = None) -> List[Dict]:
    """
    Given a list of backup dicts with 'created_at' and 'retention_days',
    return only those that have expired.
    """
    now = now or datetime.utcnow()
    expired = []
    for b in backups:
        created = b.get("created_at")
        retention = b.get("retention_days", 30)
        if isinstance(created, datetime) and not should_retain_backup(created, retention, now):
            expired.append(b)
    return expired


# ---------------------------------------------------------------------------
# GFS (Grandfather-Father-Son) Retention Logic
# ---------------------------------------------------------------------------

def apply_gfs_retention(
    backups: List[Dict],
    daily_count: int = 7,
    weekly_count: int = 4,
    monthly_count: int = 12,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Apply GFS rotation policy.
    Returns (keep, delete) lists.
    Each backup dict must have 'created_at' (datetime) and 'id'.
    """
    if not backups:
        return [], []

    sorted_backups = sorted(backups, key=lambda b: b["created_at"], reverse=True)
    keep_ids: set = set()

    # Keep N most recent (daily)
    for b in sorted_backups[:daily_count]:
        keep_ids.add(b["id"])

    # Keep weekly (first backup per week for last N weeks)
    seen_weeks: set = set()
    for b in sorted_backups:
        week_key = b["created_at"].isocalendar()[:2]  # (year, week)
        if week_key not in seen_weeks and len(seen_weeks) < weekly_count:
            seen_weeks.add(week_key)
            keep_ids.add(b["id"])

    # Keep monthly (first backup per month for last N months)
    seen_months: set = set()
    for b in sorted_backups:
        month_key = (b["created_at"].year, b["created_at"].month)
        if month_key not in seen_months and len(seen_months) < monthly_count:
            seen_months.add(month_key)
            keep_ids.add(b["id"])

    keep = [b for b in backups if b["id"] in keep_ids]
    delete = [b for b in backups if b["id"] not in keep_ids]
    return keep, delete


# ---------------------------------------------------------------------------
# Schedule Logic
# ---------------------------------------------------------------------------

def get_next_run_time(cron_expression: str, base_time: Optional[datetime] = None) -> datetime:
    """Get the next scheduled run time for a cron expression"""
    base_time = base_time or datetime.utcnow()
    cron = croniter(cron_expression, base_time)
    return cron.get_next(datetime)


def get_previous_run_time(cron_expression: str, base_time: Optional[datetime] = None) -> datetime:
    """Get the most recent past run time for a cron expression"""
    base_time = base_time or datetime.utcnow()
    cron = croniter(cron_expression, base_time)
    return cron.get_prev(datetime)


def is_schedule_overdue(cron_expression: str, last_run_at: Optional[datetime],
                        threshold_minutes: int = 30) -> bool:
    """Check if a schedule missed its last run by more than threshold_minutes"""
    if last_run_at is None:
        return True
    expected = get_previous_run_time(cron_expression)
    gap = (datetime.utcnow() - expected).total_seconds() / 60
    return gap > threshold_minutes


# ---------------------------------------------------------------------------
# Size & Storage Logic
# ---------------------------------------------------------------------------

def estimate_storage_needed(backup_size_bytes: int, copies: int = 3,
                             compression_ratio: float = 2.5) -> int:
    """Estimate total storage needed for N copies with compression"""
    compressed = math.ceil(backup_size_bytes / compression_ratio)
    return compressed * copies


def check_storage_quota(used_bytes: int, quota_bytes: int,
                         warning_threshold: float = 0.8) -> Dict[str, Any]:
    """Return storage quota status"""
    ratio = used_bytes / quota_bytes if quota_bytes > 0 else 0.0
    return {
        "used_bytes": used_bytes,
        "quota_bytes": quota_bytes,
        "used_ratio": round(ratio, 4),
        "is_warning": ratio >= warning_threshold,
        "is_full": ratio >= 1.0,
        "free_bytes": max(0, quota_bytes - used_bytes),
    }


# ---------------------------------------------------------------------------
# Verification Logic
# ---------------------------------------------------------------------------

def compute_backup_integrity_score(
    verification_results: List[Dict[str, Any]],
) -> float:
    """
    Given a list of verification check results (each with 'passed': bool),
    return a 0.0–1.0 integrity score.
    """
    if not verification_results:
        return 0.0
    passed = sum(1 for r in verification_results if r.get("passed", False))
    return round(passed / len(verification_results), 4)


def summarise_backup_health(backups: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarise health across a list of backup dicts.
    Each dict should have 'status' and optionally 'size_bytes'.
    """
    total = len(backups)
    if total == 0:
        return {"total": 0, "success_rate": 0.0, "statuses": {}}

    from collections import Counter
    statuses = Counter(b.get("status", "unknown") for b in backups)
    completed = statuses.get("completed", 0)
    return {
        "total": total,
        "success_rate": round(completed / total, 4),
        "statuses": dict(statuses),
        "total_size_bytes": sum(b.get("size_bytes", 0) or 0 for b in backups),
    }
