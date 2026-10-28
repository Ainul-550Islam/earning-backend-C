"""
Webhook Alert Service — custom HTTP webhook with HMAC-SHA256 signature
"""
import hashlib
import hmac
import json
import logging
from ._shared import get_effective_alert_log
import time
import uuid

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebhookAlertService:
    """
    Send alerts to any custom HTTP endpoint.

    Supports:
    - POST with JSON body
    - HMAC-SHA256 request signing (X-Alert-Signature header)
    - Configurable custom headers
    - Retry-safe idempotency key (X-Alert-Idempotency-Key)
    - Optional bearer token auth
    """

    @staticmethod
    def send(notification, channel):
        """
        Send alert payload to a custom webhook URL.

        channel.config expected keys:
            url            (required)  — target webhook URL (https://)
            secret         (optional)  — HMAC secret for request signing
            headers        (optional)  — dict of extra HTTP headers
            bearer_token   (optional)  — Authorization: Bearer <token>
            timeout        (optional)  — request timeout in seconds (default 10)
            method         (optional)  — HTTP method, default "POST"
            include_details (optional) — bool, include alert details JSON (default True)
        """
        try:
            config = channel.config
            url = config.get('url')
            if not url:
                logger.error("WebhookAlertService: url not configured")
                channel.record_failure()
                return False

            if not url.startswith(('http://', 'https://')):
                logger.error(f"WebhookAlertService: invalid URL scheme — {url}")
                channel.record_failure()
                return False

            alert_log = get_effective_alert_log(notification)
            rule = alert_log.rule

            # Build payload
            payload = {
                "event": "alert.triggered",
                "alert_id": alert_log.id,
                "rule": {
                    "id": rule.id,
                    "name": rule.name,
                    "alert_type": rule.alert_type,
                    "severity": rule.severity,
                },
                "trigger_value": alert_log.trigger_value,
                "threshold_value": alert_log.threshold_value,
                "message": notification.message,
                "triggered_at": alert_log.triggered_at.isoformat(),
                "is_resolved": alert_log.is_resolved,
                "notification_id": notification.id,
                "timestamp": timezone.now().isoformat(),
            }

            # Optionally include full details JSON
            if config.get('include_details', True) and alert_log.details:
                payload["details"] = alert_log.details

            body = json.dumps(payload, default=str)

            # Build headers
            headers = {
                "Content-Type": "application/json",
                "X-Alert-Idempotency-Key": str(uuid.uuid4()),
                "X-Alert-Event": "alert.triggered",
                "X-Alert-Severity": rule.severity,
            }

            # HMAC-SHA256 signature
            secret = config.get('secret')
            if secret:
                signature = WebhookAlertService._sign(body, secret)
                headers["X-Alert-Signature"] = f"sha256={signature}"

            # Bearer token auth
            bearer_token = config.get('bearer_token')
            if bearer_token:
                headers["Authorization"] = f"Bearer {bearer_token}"

            # Merge any extra custom headers (caller-supplied override last)
            extra_headers = config.get('headers', {})
            if isinstance(extra_headers, dict):
                headers.update(extra_headers)

            method = config.get('method', 'POST').upper()
            timeout = int(config.get('timeout', 10))

            resp = requests.request(
                method,
                url,
                data=body,
                headers=headers,
                timeout=timeout,
            )
            resp.raise_for_status()

            channel.record_success()
            logger.info(
                f"WebhookAlertService: {method} {url} → {resp.status_code} "
                f"for alert {alert_log.id}"
            )
            return True

        except requests.exceptions.Timeout:
            logger.error(f"WebhookAlertService: request to {config.get('url')} timed out")
            channel.record_failure()
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"WebhookAlertService: connection error — {e}")
            channel.record_failure()
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"WebhookAlertService: HTTP {e.response.status_code} from "
                f"{config.get('url')} — {e.response.text[:200]}"
            )
            channel.record_failure()
            return False
        except Exception as e:
            logger.error(f"WebhookAlertService: unexpected error — {e}")
            channel.record_failure()
            return False

    @staticmethod
    def send_resolved(alert_log, channel):
        """
        Send a resolution event to the webhook endpoint.
        Uses the same signing and header logic as send().
        """
        try:
            config = channel.config
            url = config.get('url')
            if not url:
                return False

            rule = alert_log.rule
            resolution_minutes = None
            if alert_log.resolved_at:
                resolution_minutes = (
                    alert_log.resolved_at - alert_log.triggered_at
                ).total_seconds() / 60

            payload = {
                "event": "alert.resolved",
                "alert_id": alert_log.id,
                "rule": {
                    "id": rule.id,
                    "name": rule.name,
                    "alert_type": rule.alert_type,
                    "severity": rule.severity,
                },
                "trigger_value": alert_log.trigger_value,
                "threshold_value": alert_log.threshold_value,
                "resolved_at": alert_log.resolved_at.isoformat() if alert_log.resolved_at else None,
                "resolution_note": alert_log.resolution_note,
                "resolution_minutes": resolution_minutes,
                "timestamp": timezone.now().isoformat(),
            }

            body = json.dumps(payload, default=str)

            headers = {
                "Content-Type": "application/json",
                "X-Alert-Idempotency-Key": str(uuid.uuid4()),
                "X-Alert-Event": "alert.resolved",
                "X-Alert-Severity": rule.severity,
            }

            secret = config.get('secret')
            if secret:
                headers["X-Alert-Signature"] = f"sha256={WebhookAlertService._sign(body, secret)}"

            bearer_token = config.get('bearer_token')
            if bearer_token:
                headers["Authorization"] = f"Bearer {bearer_token}"

            extra_headers = config.get('headers', {})
            if isinstance(extra_headers, dict):
                headers.update(extra_headers)

            timeout = int(config.get('timeout', 10))
            resp = requests.post(url, data=body, headers=headers, timeout=timeout)
            resp.raise_for_status()

            logger.info(f"WebhookAlertService: resolved event sent for alert {alert_log.id}")
            return True

        except Exception as e:
            logger.error(f"WebhookAlertService.send_resolved error: {e}")
            return False

    @staticmethod
    def _sign(body: str, secret: str) -> str:
        """
        Compute HMAC-SHA256 hex digest of the request body.

        Args:
            body:   JSON string of the request body
            secret: shared secret string

        Returns:
            Hex-encoded HMAC-SHA256 digest
        """
        return hmac.new(
            secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def verify_signature(body: str, secret: str, received_signature: str) -> bool:
        """
        Verify an inbound webhook signature.
        Strips the 'sha256=' prefix if present.

        Args:
            body:               raw request body string
            secret:             shared secret
            received_signature: value from X-Alert-Signature header

        Returns:
            True if signature matches, False otherwise
        """
        if received_signature.startswith('sha256='):
            received_signature = received_signature[7:]
        expected = WebhookAlertService._sign(body, secret)
        return hmac.compare_digest(expected, received_signature)
