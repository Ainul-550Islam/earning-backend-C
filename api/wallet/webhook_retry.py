# api/wallet/webhook_retry.py
"""
WebhookRetryQueue — Reliable webhook delivery with exponential backoff.

When a webhook delivery fails, it's queued for retry:
  Attempt 1: immediate
  Attempt 2: 5 minutes later
  Attempt 3: 30 minutes later
  Attempt 4: 2 hours later
  Attempt 5: 6 hours later   (final — marks DEAD if still failing)

Celery beat runs WebhookRetryQueue.process_due() every 2 minutes.
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger("wallet.webhook_retry")

# Retry delays in seconds (exponential backoff)
RETRY_DELAYS = [0, 300, 1800, 7200, 21600]   # 0, 5m, 30m, 2h, 6h
MAX_ATTEMPTS = len(RETRY_DELAYS)


def _get_secret() -> bytes:
    raw = getattr(settings, "WALLET_WEBHOOK_SECRET", "wallet-webhook-secret")
    return raw.encode() if isinstance(raw, str) else raw


def _sign_payload(payload: str) -> str:
    """HMAC-SHA256 signature for webhook payload."""
    return "sha256=" + hmac.new(_get_secret(), payload.encode(), hashlib.sha256).hexdigest()


class WebhookRetryJob(models.Model):
    """
    A single queued webhook delivery attempt.
    Immutable once created — each retry creates a new job (preserves history).
    """

    STATUS_PENDING   = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED    = "failed"
    STATUS_DEAD      = "dead"       # Max retries exhausted
    STATUS_CHOICES   = [
        (STATUS_PENDING,   "Pending"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED,    "Failed — Retrying"),
        (STATUS_DEAD,      "Dead — Max Retries"),
    ]

    job_id        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    endpoint      = models.ForeignKey(
        "wallet.WebhookEndpoint", on_delete=models.CASCADE, related_name="retry_jobs",
        null=True, blank=True,
    )
    endpoint_url  = models.URLField(help_text="Snapshot of URL at time of creation")
    event_type    = models.CharField(max_length=80, db_index=True)
    payload       = models.JSONField(default=dict)
    payload_signature = models.CharField(max_length=80, blank=True)

    attempt_number = models.PositiveSmallIntegerField(default=1)
    max_attempts   = models.PositiveSmallIntegerField(default=MAX_ATTEMPTS)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)

    status         = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True,
    )
    last_error     = models.TextField(blank=True)
    http_status    = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body  = models.TextField(blank=True)

    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_webhookretryjob"
        ordering  = ["next_attempt_at"]
        indexes   = [
            models.Index(fields=["status", "next_attempt_at"]),
            models.Index(fields=["event_type", "status"]),
        ]

    def __str__(self) -> str:
        return (
            f"Job {str(self.job_id)[:8]} | {self.event_type} | "
            f"attempt={self.attempt_number}/{self.max_attempts} | {self.status}"
        )


class WebhookRetryQueue:
    """Service to enqueue, dispatch, and retry webhooks."""

    @classmethod
    def enqueue(
        cls,
        endpoint_url: str,
        event_type: str,
        payload: dict,
        endpoint=None,
        delay_seconds: int = 0,
    ) -> WebhookRetryJob:
        """
        Enqueue a new webhook delivery.

        Args:
            endpoint_url:  Destination URL
            event_type:    e.g. "wallet_credited", "withdrawal_completed"
            payload:       Dict to send as JSON body
            endpoint:      Optional WebhookEndpoint FK
            delay_seconds: Initial delay before first attempt

        Returns: WebhookRetryJob instance
        """
        payload_str = json.dumps(payload, default=str, sort_keys=True)
        signature   = _sign_payload(payload_str)
        send_at     = timezone.now() + timedelta(seconds=delay_seconds)

        job = WebhookRetryJob.objects.create(
            endpoint=endpoint,
            endpoint_url=endpoint_url,
            event_type=event_type,
            payload=payload,
            payload_signature=signature,
            attempt_number=1,
            next_attempt_at=send_at,
            status=WebhookRetryJob.STATUS_PENDING,
        )
        logger.info(f"Webhook enqueued: event={event_type} url={endpoint_url[:50]} job={job.job_id}")
        return job

    @classmethod
    def process_due(cls, limit: int = 50) -> dict:
        """
        Process all due webhook jobs (called by Celery beat every 2 minutes).
        Returns {"processed": int, "succeeded": int, "failed": int, "dead": int}
        """
        now = timezone.now()
        due_jobs = WebhookRetryJob.objects.filter(
            status=WebhookRetryJob.STATUS_PENDING,
            next_attempt_at__lte=now,
        ).select_related("endpoint").order_by("next_attempt_at")[:limit]

        stats = {"processed": 0, "succeeded": 0, "failed": 0, "dead": 0}

        for job in due_jobs:
            result = cls._dispatch(job)
            stats["processed"] += 1
            stats[result] += 1

        return stats

    @classmethod
    def _dispatch(cls, job: WebhookRetryJob) -> str:
        """Send one webhook. Returns "succeeded" | "failed" | "dead"."""
        import requests
        payload_str = json.dumps(job.payload, default=str, sort_keys=True)

        try:
            resp = requests.post(
                job.endpoint_url,
                data=payload_str,
                headers={
                    "Content-Type":        "application/json",
                    "X-Wallet-Event":      job.event_type,
                    "X-Wallet-Signature":  job.payload_signature,
                    "X-Wallet-Attempt":    str(job.attempt_number),
                    "X-Wallet-Job-ID":     str(job.job_id),
                },
                timeout=10,
            )
            success = 200 <= resp.status_code < 300

            if success:
                job.status      = WebhookRetryJob.STATUS_SUCCEEDED
                job.http_status = resp.status_code
                job.response_body = resp.text[:500]
                job.save(update_fields=["status", "http_status", "response_body", "updated_at"])
                logger.info(f"Webhook delivered: job={job.job_id} event={job.event_type}")
                return "succeeded"

            # Non-2xx response — schedule retry
            error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            return cls._schedule_retry(job, error, http_status=resp.status_code)

        except Exception as e:
            return cls._schedule_retry(job, str(e))

    @staticmethod
    def _schedule_retry(
        job: WebhookRetryJob, error: str, http_status: int = None
    ) -> str:
        """Schedule next retry or mark dead if max attempts reached."""
        next_attempt = job.attempt_number + 1

        if next_attempt > job.max_attempts:
            job.status     = WebhookRetryJob.STATUS_DEAD
            job.last_error = error
            if http_status:
                job.http_status = http_status
            job.save(update_fields=[
                "status", "last_error", "http_status", "updated_at"
            ])
            logger.error(
                f"Webhook DEAD after {job.attempt_number} attempts: "
                f"job={job.job_id} event={job.event_type} error={error}"
            )
            return "dead"

        delay = RETRY_DELAYS[min(next_attempt - 1, len(RETRY_DELAYS) - 1)]
        WebhookRetryJob.objects.create(
            endpoint=job.endpoint,
            endpoint_url=job.endpoint_url,
            event_type=job.event_type,
            payload=job.payload,
            payload_signature=job.payload_signature,
            attempt_number=next_attempt,
            max_attempts=job.max_attempts,
            next_attempt_at=timezone.now() + timedelta(seconds=delay),
            status=WebhookRetryJob.STATUS_PENDING,
        )
        job.status     = WebhookRetryJob.STATUS_FAILED
        job.last_error = error
        if http_status:
            job.http_status = http_status
        job.save(update_fields=["status", "last_error", "http_status", "updated_at"])
        logger.warning(
            f"Webhook retry scheduled: job={job.job_id} "
            f"attempt={next_attempt} in {delay}s error={error[:80]}"
        )
        return "failed"
