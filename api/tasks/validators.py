# api/tasks/validators.py
"""
Strict validation for task-related data: URLs, metadata, reward bounds.
"""
import logging
import re
from typing import Tuple, Optional, List
from urllib.parse import urlparse
from decimal import Decimal

logger = logging.getLogger(__name__)

ALLOWED_URL_SCHEMES = ('http', 'https')
BLOCKED_HOSTS = frozenset([
    'localhost', '127.0.0.1', '0.0.0.0', '::1',
    'internal', 'local', 'metadata', '169.254.169.254',
])
MAX_URL_LENGTH = 2048
MIN_DURATION_SECONDS = 5
MAX_DURATION_SECONDS = 3600
MAX_POINTS_PER_TASK = 10000
MIN_POINTS_PER_TASK = 0


def validate_task_url(url: str) -> Tuple[bool, str]:
    """
    Strict task URL validation. Returns (is_valid, error_message).
    """
    if not url or not isinstance(url, str):
        return False, "URL is required."
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        return False, f"URL must be at most {MAX_URL_LENGTH} characters."
    try:
        parsed = urlparse(url)
    except Exception as e:
        logger.warning("urlparse failed: %s", e)
        return False, "Invalid URL format."
    if not parsed.scheme:
        return False, "URL must include scheme (http or https)."
    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        return False, f"URL scheme must be one of: {', '.join(ALLOWED_URL_SCHEMES)}."
    host = (parsed.hostname or '').lower()
    if not host:
        return False, "URL must have a valid host."
    if host in BLOCKED_HOSTS:
        return False, "This URL host is not allowed for tasks."
    if host.startswith('192.168.') or host.startswith('10.') or host.startswith('172.'):
        return False, "Private network URLs are not allowed."
    return True, ""


def validate_duration_seconds(value: Optional[int]) -> Tuple[bool, str]:
    """Validate task duration in seconds."""
    if value is None:
        return True, ""
    try:
        n = int(value)
        if n < MIN_DURATION_SECONDS:
            return False, f"Duration must be at least {MIN_DURATION_SECONDS} seconds."
        if n > MAX_DURATION_SECONDS:
            return False, f"Duration must be at most {MAX_DURATION_SECONDS} seconds."
        return True, ""
    except (TypeError, ValueError):
        return False, "Duration must be a number."


def validate_reward_points(value: Optional[float]) -> Tuple[bool, str]:
    """Validate reward points for a task."""
    if value is None:
        return True, ""
    try:
        n = float(value)
        if n < MIN_POINTS_PER_TASK:
            return False, f"Points must be at least {MIN_POINTS_PER_TASK}."
        if n > MAX_POINTS_PER_TASK:
            return False, f"Points must be at most {MAX_POINTS_PER_TASK}."
        return True, ""
    except (TypeError, ValueError):
        return False, "Points must be a number."
