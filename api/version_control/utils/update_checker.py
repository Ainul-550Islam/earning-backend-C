# =============================================================================
# version_control/utils/update_checker.py
# =============================================================================
"""
Utility functions for in-process update checks.

These helpers are used by the middleware and viewsets to quickly determine
update status without going through the full VersionCheckService.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..constants import VERSION_REGEX

logger = logging.getLogger(__name__)


def is_valid_version(version: str) -> bool:
    """Return True if `version` is a valid semver string."""
    return bool(version and re.match(VERSION_REGEX, version.strip()))


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two semver strings.

    Returns:
        -1  if v1 < v2
         0  if v1 == v2
        +1  if v1 > v2

    Ignores pre-release / build metadata.
    """
    def _parse(v: str) -> tuple[int, int, int]:
        m = re.match(r"^(\d+)\.(\d+)\.(\d+)", v)
        if not m:
            raise ValueError(f"Cannot parse version: {v!r}")
        return int(m[1]), int(m[2]), int(m[3])

    t1 = _parse(v1)
    t2 = _parse(v2)

    if t1 < t2:
        return -1
    if t1 > t2:
        return 1
    return 0


def client_needs_update(client_version: str, target_version: str) -> bool:
    """
    Return True if client_version is strictly less than target_version.
    Returns False on any parse error (fail-open).
    """
    try:
        return compare_versions(client_version, target_version) < 0
    except ValueError:
        logger.warning(
            "client_needs_update.parse_failed client=%s target=%s",
            client_version, target_version,
        )
        return False


def get_update_urgency(client_version: str, target_version: str) -> str:
    """
    Heuristic urgency based on semver delta:
      major bump → critical
      minor bump → required
      patch bump → optional
    Assumes client < target (call client_needs_update first).
    """
    try:
        def _parse(v: str) -> tuple[int, int, int]:
            m = re.match(r"^(\d+)\.(\d+)\.(\d+)", v)
            if not m:
                return (0, 0, 0)
            return int(m[1]), int(m[2]), int(m[3])

        c_maj, c_min, c_pat = _parse(client_version)
        t_maj, t_min, t_pat = _parse(target_version)

        if t_maj > c_maj:
            return "critical"
        if t_min > c_min:
            return "required"
        return "optional"
    except Exception:
        return "optional"
