"""Input Validators for DR System."""
import re
from datetime import datetime
from typing import Any

def validate_cron_expression(expr: str) -> bool:
    """Validate a cron expression (5 or 6 fields)."""
    try:
        from croniter import croniter
        return croniter.is_valid(expr)
    except ImportError:
        parts = expr.split()
        return len(parts) in (5, 6)

def validate_backup_type(value: str) -> bool:
    from .enums import BackupType
    return value in [t.value for t in BackupType]

def validate_storage_path(path: str) -> bool:
    if not path:
        return False
    invalid_chars = set('<>:"|?*')
    return not any(c in invalid_chars for c in path) and len(path) < 1000

def validate_database_name(name: str) -> bool:
    return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$", name))

def validate_retention_days(days: int) -> bool:
    return 1 <= days <= 3650

def validate_point_in_time(dt: datetime, earliest: datetime, latest: datetime) -> bool:
    return earliest <= dt <= latest

def validate_rto_seconds(rto: int) -> bool:
    return 60 <= rto <= 86400 * 30  # 1 min to 30 days

def validate_rpo_seconds(rpo: int) -> bool:
    return 0 <= rpo <= 86400  # 0 to 24 hours
