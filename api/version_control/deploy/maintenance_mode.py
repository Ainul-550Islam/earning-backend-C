# =============================================================================
# version_control/deploy/maintenance_mode.py
# =============================================================================
"""
Deployment helper for enabling / disabling maintenance mode programmatically.

Designed for use in CI/CD pipelines, pre-deploy hooks, and Fabric/Ansible
scripts.  Communicates with the app via its own REST API so it works even
from outside the Django process.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone as py_tz, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MaintenanceResult:
    success:     bool
    schedule_id: str | None = None
    error:       str | None = None
    data:        dict | None = None


class MaintenanceModeManager:
    """
    Programmatic maintenance mode toggle via REST API.

    Usage::

        mgr = MaintenanceModeManager(
            base_url="https://api.myapp.com/api/version",
            auth_token="Bearer <staff-token>",
        )
        # Start a 30-minute maintenance window immediately
        result = mgr.start_now(title="Deploy v2.0.0", duration_minutes=30)
        ... do deploy ...
        mgr.end(result.schedule_id)
    """

    def __init__(
        self,
        base_url: str,
        auth_token: str,
        timeout: int = 15,
    ) -> None:
        self.base_url   = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout    = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_now(
        self,
        title: str,
        duration_minutes: int = 60,
        platforms: list[str] | None = None,
        description: str = "",
    ) -> MaintenanceResult:
        """
        Create AND immediately activate a maintenance window.

        1. POST /maintenance/   → create scheduled window
        2. POST /maintenance/{id}/start/ → activate it
        """
        now   = datetime.now(tz=py_tz.utc)
        end   = now + timedelta(minutes=duration_minutes)

        payload = {
            "title":           title,
            "description":     description,
            "platforms":       platforms or [],
            "scheduled_start": now.isoformat(),
            "scheduled_end":   end.isoformat(),
            "notify_users":    False,
        }

        create_result = self._post(f"{self.base_url}/maintenance/", payload)
        if not create_result["ok"]:
            return MaintenanceResult(
                success=False,
                error=f"Create failed: {create_result['error']}",
            )

        schedule_id = create_result["data"].get("id")
        if not schedule_id:
            return MaintenanceResult(success=False, error="No ID in create response.")

        start_result = self._post(
            f"{self.base_url}/maintenance/{schedule_id}/start/", {}
        )
        if not start_result["ok"]:
            return MaintenanceResult(
                success=False,
                schedule_id=schedule_id,
                error=f"Start failed: {start_result['error']}",
            )

        logger.info("maintenance.started_via_api id=%s title=%r", schedule_id, title)
        return MaintenanceResult(
            success=True,
            schedule_id=schedule_id,
            data=start_result["data"],
        )

    def end(self, schedule_id: str) -> MaintenanceResult:
        """End an active maintenance window by its schedule ID."""
        result = self._post(
            f"{self.base_url}/maintenance/{schedule_id}/end/", {}
        )
        if not result["ok"]:
            return MaintenanceResult(
                success=False,
                schedule_id=schedule_id,
                error=result["error"],
            )
        logger.info("maintenance.ended_via_api id=%s", schedule_id)
        return MaintenanceResult(success=True, schedule_id=schedule_id, data=result["data"])

    def cancel(self, schedule_id: str) -> MaintenanceResult:
        """Cancel a scheduled (not yet active) maintenance window."""
        result = self._post(
            f"{self.base_url}/maintenance/{schedule_id}/cancel/", {}
        )
        if not result["ok"]:
            return MaintenanceResult(
                success=False,
                schedule_id=schedule_id,
                error=result["error"],
            )
        return MaintenanceResult(success=True, schedule_id=schedule_id)

    def is_active(self, platform: str = "web") -> bool:
        """Check whether maintenance is currently active (public endpoint)."""
        url = f"{self.base_url}/maintenance/status/?platform={platform}"
        try:
            req  = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
                return bool(data.get("is_active", False))
        except Exception as exc:
            logger.warning("maintenance.is_active_check_failed error=%s", exc)
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _post(self, url: str, payload: dict) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        req  = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type":  "application/json",
                "Authorization": self.auth_token,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode()
            logger.error(
                "maintenance_api.post_error url=%s status=%d body=%s",
                url, exc.code, error_body,
            )
            return {"ok": False, "error": f"HTTP {exc.code}: {error_body}"}
        except Exception as exc:
            logger.exception("maintenance_api.post_unexpected url=%s", url)
            return {"ok": False, "error": str(exc)}
