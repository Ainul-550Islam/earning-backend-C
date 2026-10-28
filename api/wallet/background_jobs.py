# api/wallet/background_jobs.py
"""
Background job management — track, monitor, and retry background Celery tasks.
"""
import logging
import uuid
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("wallet.background_jobs")
JOB_TTL = 86400


class BackgroundJob:
    """Track and monitor a background Celery job."""

    @staticmethod
    def submit(task_func, *args, **kwargs) -> str:
        """Submit a Celery task and track it."""
        job_id = str(uuid.uuid4())
        try:
            result = task_func.apply_async(args=args, kwargs=kwargs)
            cache.set(f"job:{job_id}", {
                "job_id":    job_id,
                "task_id":   str(result.id),
                "task_name": task_func.name,
                "status":    "submitted",
                "submitted": timezone.now().isoformat(),
                "args":      str(args)[:200],
            }, JOB_TTL)
            logger.info(f"Job submitted: {job_id} → task={result.id}")
        except Exception as e:
            cache.set(f"job:{job_id}", {"job_id": job_id, "status": "failed", "error": str(e)}, JOB_TTL)
        return job_id

    @staticmethod
    def get_status(job_id: str) -> dict:
        """Get job status."""
        data = cache.get(f"job:{job_id}") or {}
        if data.get("task_id"):
            try:
                from celery.result import AsyncResult
                result = AsyncResult(data["task_id"])
                data["celery_status"] = result.status
                data["result"] = str(result.result)[:500] if result.ready() else None
            except Exception:
                pass
        return data

    @staticmethod
    def list_recent(limit: int = 20) -> list:
        """List recent jobs (requires Redis pattern scan)."""
        try:
            keys = cache.client.get_client().scan_iter("job:*", count=100)
            jobs = []
            for key in list(keys)[:limit]:
                raw = cache.get(key.decode().replace("job:", ""))
                if raw:
                    jobs.append(raw)
            return sorted(jobs, key=lambda x: x.get("submitted", ""), reverse=True)
        except Exception:
            return []

    @staticmethod
    def cancel(job_id: str) -> bool:
        """Cancel a queued job."""
        data = cache.get(f"job:{job_id}")
        if data and data.get("task_id"):
            try:
                from celery.result import AsyncResult
                AsyncResult(data["task_id"]).revoke(terminate=True)
                data["status"] = "cancelled"
                cache.set(f"job:{job_id}", data, JOB_TTL)
                return True
            except Exception as e:
                logger.error(f"Cancel job {job_id}: {e}")
        return False
