"""
Backup Module Helpers
Common helper functions used across the backup module.
"""

import os
import re
import uuid
import hashlib
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# String Helpers
# ---------------------------------------------------------------------------

def slugify_backup_name(name: str) -> str:
    """Convert a backup name to a safe filesystem slug"""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def generate_backup_filename(prefix: str = "backup", extension: str = ".sql") -> str:
    """Generate a unique timestamped filename"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    name = f"{slugify_backup_name(prefix)}_{timestamp}_{unique_id}{extension}"
    return name


def truncate_string(s: str, max_length: int = 255, suffix: str = "...") -> str:
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


# ---------------------------------------------------------------------------
# Size Helpers
# ---------------------------------------------------------------------------

def bytes_to_human(size_bytes: int) -> str:
    """Convert bytes to human-readable string"""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {units[i]}"


def parse_size_string(size_str: str) -> int:
    """Parse human-readable size string to bytes. E.g. '100MB' -> 104857600"""
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)", size_str.strip().upper())
    if not match:
        raise ValueError(f"Cannot parse size string: {size_str!r}")
    value, unit = match.groups()
    return int(float(value) * units[unit])


# ---------------------------------------------------------------------------
# File Helpers
# ---------------------------------------------------------------------------

def compute_file_checksum(file_path: str, algorithm: str = "sha256") -> str:
    """Compute checksum of a file"""
    h = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_directory(path: str) -> str:
    """Create directory if it does not exist, return path"""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def safe_delete_file(path: str) -> bool:
    """Delete a file, return True on success"""
    try:
        os.unlink(path)
        return True
    except OSError as exc:
        logger.warning("Could not delete %s: %s", path, exc)
        return False


def get_file_age_days(path: str) -> Optional[float]:
    """Return age of a file in days, or None if file not found"""
    try:
        mtime = os.path.getmtime(path)
        age_seconds = (datetime.utcnow() - datetime.utcfromtimestamp(mtime)).total_seconds()
        return age_seconds / 86400
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Time Helpers
# ---------------------------------------------------------------------------

def parse_duration(duration_str: str) -> timedelta:
    """
    Parse a duration string like '2d', '4h', '30m', '90s' to timedelta.
    """
    pattern = re.compile(r"^(\d+)(d|h|m|s)$", re.IGNORECASE)
    match = pattern.match(duration_str.strip())
    if not match:
        raise ValueError(f"Invalid duration string: {duration_str!r}. Use e.g. '2d', '4h', '30m'.")
    value, unit = int(match.group(1)), match.group(2).lower()
    mapping = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds"}
    return timedelta(**{mapping[unit]: value})


def humanize_duration(td: timedelta) -> str:
    """Convert timedelta to human-readable string"""
    total_seconds = int(td.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    if total_seconds < 3600:
        return f"{total_seconds // 60}m {total_seconds % 60}s"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    return f"{days}d {hours}h"


# ---------------------------------------------------------------------------
# Dict / JSON Helpers
# ---------------------------------------------------------------------------

def deep_merge(base: Dict, override: Dict) -> Dict:
    """Recursively merge override into base, returning a new dict"""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def flatten_dict(d: Dict, parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Flatten a nested dict with dot-notation keys"""
    items: List = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def mask_sensitive(data: Dict, sensitive_keys: Optional[List[str]] = None) -> Dict:
    """Replace sensitive values with '***'"""
    sensitive_keys = sensitive_keys or [
        "password", "secret", "api_key", "access_key", "token", "credentials"
    ]
    result = {}
    for key, value in data.items():
        if any(s in key.lower() for s in sensitive_keys):
            result[key] = "***"
        elif isinstance(value, dict):
            result[key] = mask_sensitive(value, sensitive_keys)
        else:
            result[key] = value
    return result
