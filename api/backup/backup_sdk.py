"""
Backup System Python SDK
Client library for B2B customers to integrate backup management
into their own applications and workflows.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import requests

logger = logging.getLogger(__name__)

__version__ = "1.0.0"
__all__ = ["BackupClient", "BackupSDKError", "RateLimitError", "AuthError"]


class BackupSDKError(Exception):
    """Base SDK exception"""
    def __init__(self, message: str, status_code: int = 0,
                 response: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class AuthError(BackupSDKError):
    """Authentication / authorisation failure"""


class RateLimitError(BackupSDKError):
    """API rate limit exceeded"""
    def __init__(self, retry_after: int = 60):
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s.", 429)
        self.retry_after = retry_after


class NotFoundError(BackupSDKError):
    """Resource not found"""


# ── Response models ────────────────────────────────────────────────────────────

@dataclass
class BackupObject:
    id: str
    name: str
    status: str
    size_bytes: Optional[int]
    created_at: str
    storage_type: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BackupObject":
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            status=d.get("status", ""),
            size_bytes=d.get("size_bytes") or d.get("file_size"),
            created_at=d.get("created_at", ""),
            storage_type=d.get("storage_type", ""),
            raw=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name,
            "status": self.status,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
            "storage_type": self.storage_type,
        }


@dataclass
class ScheduleObject:
    id: str
    name: str
    cron_expression: str
    is_active: bool
    next_run_at: Optional[str]
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScheduleObject":
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            cron_expression=d.get("cron_expression", ""),
            is_active=d.get("is_active", False),
            next_run_at=d.get("next_run_at"),
            raw=d,
        )


@dataclass
class PaginatedResponse:
    items: List[Any]
    count: int
    next: Optional[str]
    previous: Optional[str]


# ── Main client ────────────────────────────────────────────────────────────────

class BackupClient:
    """
    Python SDK for the Backup System REST API.
    Supports API key auth, automatic retry, pagination, and webhooks.

    Usage:
        client = BackupClient(api_key="bk_live_xxxx", base_url="https://api.backupsystem.io")
        backups = client.backups.list(status="completed")
        job = client.backups.create(name="prod_db", storage="s3")
        client.backups.restore(job.id, target_db="prod_restored")
    """

    DEFAULT_TIMEOUT = 30
    DEFAULT_RETRIES = 3
    SDK_USER_AGENT = f"BackupSystem-Python-SDK/{__version__}"

    def __init__(self, api_key: str, base_url: str = "https://api.backupsystem.io",
                 timeout: int = DEFAULT_TIMEOUT, max_retries: int = DEFAULT_RETRIES):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": self.SDK_USER_AGENT,
            "Accept": "application/json",
        })
        # Resource namespaces
        self.backups   = _BackupResource(self)
        self.schedules = _ScheduleResource(self)
        self.storage   = _StorageResource(self)
        self.reports   = _ReportResource(self)
        self.webhooks  = _WebhookResource(self)

    def _request(self, method: str, path: str,
                 params: Optional[Dict] = None,
                 json_body: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.request(
                    method, url, params=params,
                    json=json_body, timeout=self.timeout,
                )
                if resp.status_code == 401:
                    raise AuthError("Invalid API key or insufficient permissions", 401)
                if resp.status_code == 404:
                    raise NotFoundError(f"Resource not found: {path}", 404)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after)
                if not resp.ok:
                    raise BackupSDKError(
                        f"API error {resp.status_code}: {resp.text[:200]}",
                        resp.status_code,
                    )
                return resp.json() if resp.content else {}
            except (AuthError, NotFoundError, RateLimitError):
                raise
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning("SDK request attempt %d/%d failed: %s",
                               attempt, self.max_retries, exc)
                if attempt == self.max_retries:
                    raise BackupSDKError(f"Request failed after {self.max_retries} retries: {exc}")
        raise BackupSDKError(f"Request failed: {last_exc}")

    def get(self, path: str, params: Optional[Dict] = None) -> Dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: Optional[Dict] = None) -> Dict:
        return self._request("POST", path, json_body=body)

    def patch(self, path: str, body: Optional[Dict] = None) -> Dict:
        return self._request("PATCH", path, json_body=body)

    def delete(self, path: str) -> Dict:
        return self._request("DELETE", path)

    def paginate(self, path: str, params: Optional[Dict] = None,
                 page_size: int = 50) -> Iterator[Dict]:
        """Auto-paginate through all pages of a list endpoint"""
        params = params or {}
        params["page_size"] = page_size
        while True:
            data = self.get(path, params=params)
            for item in data.get("results", []):
                yield item
            next_url = data.get("next")
            if not next_url:
                break
            # Extract page param from next URL
            import urllib.parse as urlp
            q = urlp.urlparse(next_url).query
            p = dict(urlp.parse_qsl(q))
            params.update(p)

    def health(self) -> Dict[str, Any]:
        """Check API connectivity and authentication"""
        return self.get("/api/public/health-check/")


# ── Resource classes ───────────────────────────────────────────────────────────

class _BackupResource:
    def __init__(self, client: BackupClient):
        self._c = client

    def list(self, status: Optional[str] = None,
              page_size: int = 20) -> List[BackupObject]:
        params = {"page_size": page_size}
        if status:
            params["status"] = status
        data = self._c.get("/api/backups/", params=params)
        return [BackupObject.from_dict(b) for b in data.get("results", [])]

    def get(self, backup_id: str) -> BackupObject:
        data = self._c.get(f"/api/backups/{backup_id}/")
        return BackupObject.from_dict(data)

    def create(self, name: str, storage_type: str = "s3",
               backup_type: str = "full",
               retention_days: int = 30, **kwargs) -> BackupObject:
        body = {
            "name": name,
            "storage_type": storage_type,
            "backup_type": backup_type,
            "retention_days": retention_days,
            **kwargs,
        }
        data = self._c.post("/api/backups/", body=body)
        return BackupObject.from_dict(data)

    def delete(self, backup_id: str) -> bool:
        self._c.delete(f"/api/backups/{backup_id}/")
        return True

    def restore(self, backup_id: str, target_database: Optional[str] = None,
                dry_run: bool = False) -> Dict[str, Any]:
        body = {"target_database": target_database, "dry_run": dry_run}
        return self._c.post(f"/api/backups/{backup_id}/restore/", body=body)

    def verify(self, backup_id: str) -> Dict[str, Any]:
        return self._c.post(f"/api/backups/{backup_id}/verify/")

    def download_url(self, backup_id: str) -> str:
        data = self._c.get(f"/api/backups/{backup_id}/download/")
        return data.get("download_url", "")

    def stream_all(self, **filters) -> Iterator[BackupObject]:
        for raw in self._c.paginate("/api/backups/", params=filters):
            yield BackupObject.from_dict(raw)


class _ScheduleResource:
    def __init__(self, client: BackupClient):
        self._c = client

    def list(self, active_only: bool = True) -> List[ScheduleObject]:
        params = {"is_active": "true"} if active_only else {}
        data = self._c.get("/api/backup-schedules/", params=params)
        return [ScheduleObject.from_dict(s) for s in data.get("results", [])]

    def create(self, name: str, cron_expression: str,
               storage_type: str = "s3",
               retention_days: int = 30) -> ScheduleObject:
        body = {
            "name": name,
            "cron_expression": cron_expression,
            "storage_type": storage_type,
            "retention_days": retention_days,
        }
        data = self._c.post("/api/backup-schedules/", body=body)
        return ScheduleObject.from_dict(data)

    def pause(self, schedule_id: str) -> bool:
        self._c.post(f"/api/backup-schedules/{schedule_id}/pause/")
        return True

    def resume(self, schedule_id: str) -> bool:
        self._c.post(f"/api/backup-schedules/{schedule_id}/resume/")
        return True

    def run_now(self, schedule_id: str) -> Dict[str, Any]:
        return self._c.post(f"/api/backup-schedules/{schedule_id}/run-now/")


class _StorageResource:
    def __init__(self, client: BackupClient):
        self._c = client

    def list(self) -> List[Dict]:
        return self._c.get("/api/storage-locations/").get("results", [])

    def test_connection(self, storage_id: str) -> bool:
        result = self._c.post(f"/api/storage-locations/{storage_id}/test-connection/")
        return result.get("connected", False)


class _ReportResource:
    def __init__(self, client: BackupClient):
        self._c = client

    def summary(self, days: int = 30) -> Dict[str, Any]:
        return self._c.get("/api/dashboard/stats/", params={"days": days})

    def compliance(self) -> Dict[str, Any]:
        return self._c.get("/api/reports/compliance/")


class _WebhookResource:
    def __init__(self, client: BackupClient):
        self._c = client

    def list(self) -> List[Dict]:
        return self._c.get("/api/webhooks/").get("results", [])

    def create(self, url: str, events: List[str],
               secret: Optional[str] = None) -> Dict[str, Any]:
        return self._c.post("/api/webhooks/", body={
            "url": url, "events": events, "secret": secret,
        })

    def delete(self, webhook_id: str) -> bool:
        self._c.delete(f"/api/webhooks/{webhook_id}/")
        return True
