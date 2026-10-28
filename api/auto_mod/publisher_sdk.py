# =============================================================================
# api/auto_mod/publisher_sdk.py
# =============================================================================
"""
Publisher SDK — lightweight Python client for external publishers to integrate
with the auto_mod API without needing to build raw HTTP calls.

Usage (external publisher):
    from api.auto_mod.publisher_sdk import AutoModSDK

    sdk = AutoModSDK(api_key="your_key", base_url="https://yourplatform.com")
    result = sdk.submit_proof(
        content_id="task_123",
        submission_type="task_proof",
        file_urls=["https://...screenshot.png"],
        text_content="I completed the task as shown",
    )
    print(result.status)  # "pending" | "auto_approved" | "rejected"
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("auto_mod.publisher_sdk")


# =============================================================================
# SDK Data Classes
# =============================================================================

@dataclass
class SubmissionResult:
    submission_id: str
    status:        str
    confidence:    float = 0.0
    risk_level:    str   = "unknown"
    message:       str   = ""
    metadata:      dict  = field(default_factory=dict)

    @property
    def is_approved(self)  -> bool: return "approved" in self.status
    @property
    def is_rejected(self)  -> bool: return "rejected" in self.status
    @property
    def needs_review(self) -> bool: return self.status == "human_review"


@dataclass
class AppealResult:
    appeal_id: str
    status:    str
    message:   str = ""


@dataclass
class ModerationStatusResult:
    submission_id: str
    status:        str
    decision:      str = ""
    reviewed_at:   str = ""


# =============================================================================
# AutoModSDK
# =============================================================================

class AutoModSDK:
    """
    Lightweight Python SDK for the auto_mod REST API.

    Designed for external publishers who need to:
      1. Submit task proofs for moderation
      2. Poll submission status
      3. File appeals
      4. Receive webhook callbacks

    Authentication: HMAC-signed requests (API key + timestamp).
    """

    VERSION = "1.0.0"
    TIMEOUT = 30  # seconds

    def __init__(
        self,
        api_key:  str,
        secret:   str = "",
        base_url: str = "http://localhost:8000",
        timeout:  int = TIMEOUT,
    ):
        self.api_key  = api_key
        self.secret   = secret
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout
        self._session_headers = {
            "Content-Type":  "application/json",
            "X-API-Key":     api_key,
            "X-SDK-Version": self.VERSION,
        }

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _sign_request(self, body: str) -> dict:
        ts = str(int(time.time()))
        if self.secret:
            sig = hmac.new(
                self.secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256
            ).hexdigest()
        else:
            sig = ""
        return {"X-Timestamp": ts, "X-Signature": sig}

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, data: dict | None = None) -> dict:
        url    = f"{self.base_url}/api/auto_mod/{path.lstrip('/')}"
        body   = json.dumps(data or {}).encode()
        headers = {**self._session_headers, **self._sign_request(body.decode())}
        req     = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise AutoModSDKError(f"HTTP {e.code}: {e.read().decode()[:200]}") from e
        except Exception as e:
            raise AutoModSDKError(str(e)) from e

    def _get(self, path: str)              -> dict: return self._request("GET",    path)
    def _post(self, path: str, data: dict) -> dict: return self._request("POST",   path, data)
    def _patch(self, path: str, data: dict)-> dict: return self._request("PATCH",  path, data)

    # ── Public API ────────────────────────────────────────────────────────────

    def submit_proof(
        self,
        content_id:      str,
        submission_type: str,
        file_urls:       list[str] | None = None,
        text_content:    str = "",
        metadata:        dict | None = None,
    ) -> SubmissionResult:
        """
        Submit a task proof for moderation.

        Returns SubmissionResult with initial status.
        Status may be: pending | scanning | auto_approved | auto_rejected | human_review
        """
        payload = {
            "content_id":      content_id,
            "submission_type": submission_type,
            "file_urls":       file_urls or [],
            "text_content":    text_content,
            "metadata":        metadata or {},
        }
        resp = self._post("submissions/", payload)
        return SubmissionResult(
            submission_id=resp.get("id", ""),
            status=resp.get("status", "pending"),
            confidence=float(resp.get("ai_confidence", 0)),
            risk_level=resp.get("risk_level", "unknown"),
            metadata=resp.get("metadata", {}),
        )

    def get_status(self, submission_id: str) -> ModerationStatusResult:
        """Poll the current moderation status of a submission."""
        resp = self._get(f"submissions/{submission_id}/")
        decision_data = resp.get("decisions", [{}])
        latest = decision_data[-1] if decision_data else {}
        return ModerationStatusResult(
            submission_id=submission_id,
            status=resp.get("status", "unknown"),
            decision=latest.get("decision_type", ""),
            reviewed_at=latest.get("decided_at", ""),
        )

    def file_appeal(
        self,
        submission_id: str,
        reason:        str,
        evidence_urls: list[str] | None = None,
        additional_data: dict | None = None,
    ) -> AppealResult:
        """File an appeal for a rejected submission."""
        # Fetch latest decision
        submission = self._get(f"submissions/{submission_id}/")
        decisions  = submission.get("decisions", [])
        if not decisions:
            raise AutoModSDKError(f"No decisions found for submission {submission_id}")
        decision_id = decisions[-1]["id"]

        payload = {
            "original_decision": decision_id,
            "submission":        submission_id,
            "reason":            reason,
            "additional_data":   additional_data or {},
        }
        resp = self._post("appeals/", payload)
        return AppealResult(
            appeal_id=resp.get("id", ""),
            status=resp.get("status", "pending"),
        )

    def get_appeal_status(self, appeal_id: str) -> AppealResult:
        resp = self._get(f"appeals/{appeal_id}/")
        return AppealResult(
            appeal_id=appeal_id,
            status=resp.get("status", "unknown"),
            message=resp.get("final_reason", ""),
        )

    def list_submissions(
        self,
        status:          str = "",
        submission_type: str = "",
        limit:           int = 50,
    ) -> list[ModerationStatusResult]:
        params = f"?limit={limit}"
        if status:          params += f"&status={status}"
        if submission_type: params += f"&submission_type={submission_type}"
        resp = self._get(f"submissions/{params}")
        return [
            ModerationStatusResult(
                submission_id=s["id"],
                status=s.get("status", ""),
            )
            for s in resp.get("results", resp if isinstance(resp, list) else [])
        ]

    # ── Webhook verification ──────────────────────────────────────────────────

    def verify_webhook_signature(self, payload: str, signature: str,
                                  timestamp: str) -> bool:
        """
        Verify an incoming webhook from the platform.
        Call this in your webhook receiver endpoint.
        """
        if not self.secret:
            return True  # no secret configured → accept all
        expected = hmac.new(
            self.secret.encode(),
            f"{timestamp}.{payload}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


class AutoModSDKError(Exception):
    """Raised when the SDK encounters an error (HTTP, auth, etc.)."""
