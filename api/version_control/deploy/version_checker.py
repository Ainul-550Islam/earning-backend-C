# =============================================================================
# version_control/deploy/version_checker.py
# =============================================================================
"""
Deployment-time version checker utility.

Used in CI/CD pipelines and management commands to:
  1. Verify that the current codebase version is consistent with DB policies.
  2. Detect if any CRITICAL policies are active (block deployment if needed).
  3. Generate a deployment readiness report.

This module has NO Django ORM dependency by default — it talks to the
REST API so it can be used from outside the Django process (e.g. a
GitHub Actions step).

For in-process use, set USE_ORM=True to query the DB directly.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class VersionCheckReport:
    platform:       str
    client_version: str
    update_required: bool
    update_type:    str | None
    target_version: str | None
    release_notes:  str | None
    errors:         list[str] = field(default_factory=list)
    raw:            dict      = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        return self.update_type == "critical"

    @property
    def is_ok(self) -> bool:
        return not self.update_required and not self.errors


class DeploymentVersionChecker:
    """
    Checks update policies via the version-check REST endpoint.

    Usage in a deploy script::

        checker = DeploymentVersionChecker(
            base_url="https://api.myapp.com/api/version",
        )
        report = checker.check(platform="ios", version="2.1.0")
        if report.is_critical:
            sys.exit(1)
    """

    def __init__(self, base_url: str, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

    def check(self, platform: str, version: str) -> VersionCheckReport:
        url = (
            f"{self.base_url}/check/"
            f"?platform={platform}&version={version}"
        )
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data: dict = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode()
            logger.error(
                "version_checker.http_error status=%d body=%s",
                exc.code, error_body,
            )
            return VersionCheckReport(
                platform=platform,
                client_version=version,
                update_required=False,
                update_type=None,
                target_version=None,
                release_notes=None,
                errors=[f"HTTP {exc.code}: {error_body}"],
            )
        except Exception as exc:
            logger.exception("version_checker.request_failed")
            return VersionCheckReport(
                platform=platform,
                client_version=version,
                update_required=False,
                update_type=None,
                target_version=None,
                release_notes=None,
                errors=[str(exc)],
            )

        return VersionCheckReport(
            platform=platform,
            client_version=version,
            update_required=data.get("update_required", False),
            update_type=data.get("update_type"),
            target_version=data.get("target_version"),
            release_notes=data.get("release_notes"),
            raw=data,
        )

    def check_all_platforms(
        self,
        versions: dict[str, str],
    ) -> list[VersionCheckReport]:
        """
        Check multiple platforms at once.
        `versions` is a dict of {platform: current_version}.
        Returns a list of VersionCheckReport (one per platform).
        """
        reports = []
        for platform, version in versions.items():
            reports.append(self.check(platform=platform, version=version))
        return reports

    def has_blocking_update(self, reports: list[VersionCheckReport]) -> bool:
        """Return True if any report indicates a critical update is required."""
        return any(r.is_critical for r in reports)
