"""
tasks/internet_check_tasks.py
═══════════════════════════════════════════════════════════════════════════════
Internet Connectivity + Task Aging System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Four distinct concerns:

1. INTERNET CHECK — is the server actually online?
   • check_internet_connectivity()      runs every 60 s (beat)
   • _multi_probe_internet()            tries 5 endpoints; needs 2/5 to pass
   • CircuitBreaker integration         → pauses outbound tasks when offline

2. AGING TASKS — tasks that went stale / never finished
   • detect_aging_tasks()               finds started tasks > X minutes old
   • auto_recover_aging_tasks()         releases locks, re-queues, notifies
   • aging_report()                     returns structured data for dashboard

3. LOCK AGING — exclusive locks held past deadline
   • expire_stale_task_locks()          releases expired TaskLock rows
   • force_release_stuck_lock()         admin-triggered hard release

4. CONNECTIVITY-AWARE TASK GATE
   • ConnectivityGate                   decorator — skips task body if offline
   • queue_when_online()                deferred retry after connectivity restored
"""

import logging
import socket
import time
from datetime import timedelta
from decimal import Decimal
from typing import Optional

import requests
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

CONNECTIVITY_CACHE_KEY   = "internet_connectivity_status"
CONNECTIVITY_CACHE_TTL   = 120          # 2 min — reuse probe result
CONNECTIVITY_LOCK_KEY    = "internet_connectivity_lock"

PROBE_URLS = [                          # 5 diverse probes (DNS + HTTP)
    ("https://1.1.1.1", 3),            # Cloudflare DNS over HTTPS — fastest
    ("https://8.8.8.8", 3),            # Google DNS over HTTPS
    ("https://www.google.com", 4),
    ("https://httpbin.org/get", 5),
    ("https://api64.ipify.org", 5),
]
PROBE_PASS_THRESHOLD = 2               # Need ≥ 2/5 probes to succeed

AGING_STARTED_THRESHOLD_MINUTES  = 30  # task 'started' this long → aging
AGING_PENDING_THRESHOLD_HOURS    = 2   # task 'pending' this long  → aging
AGING_AUTO_RECOVER_THRESHOLD_MIN = 60  # older than this → auto-recover
LOCK_STALE_THRESHOLD_MINUTES     = 60  # lock held > 60 min → force-release

CACHE_TTL = 300  # 5 min


# ══════════════════════════════════════════════════════════════════════════════
# 1. INTERNET CONNECTIVITY CHECK
# ══════════════════════════════════════════════════════════════════════════════

def _multi_probe_internet() -> dict:
    """
    Fire ≥ 2 independent HTTP probes in sequence.
    Returns: { online, passed, failed, latency_ms, probed_at, details }
    Designed to be fast — stops as soon as PROBE_PASS_THRESHOLD reached.
    """
    passed   = 0
    failed   = 0
    details  = []
    best_ms  = None

    for url, timeout in PROBE_URLS:
        try:
            start    = time.monotonic()
            r        = requests.get(url, timeout=timeout)
            latency  = (time.monotonic() - start) * 1000
            ok       = r.status_code < 500
            passed  += 1 if ok else 0
            failed  += 0 if ok else 1
            if ok and best_ms is None:
                best_ms = round(latency, 1)
            details.append({"url": url, "ok": ok, "ms": round(latency, 1)})
            if passed >= PROBE_PASS_THRESHOLD:
                break  # enough confirmed — don't waste time
        except Exception as e:
            failed += 1
            details.append({"url": url, "ok": False, "error": str(e)[:80]})

    online = passed >= PROBE_PASS_THRESHOLD
    return {
        "online":      online,
        "passed":      passed,
        "failed":      failed,
        "latency_ms":  best_ms,
        "probed_at":   timezone.now().isoformat(),
        "details":     details,
    }


@shared_task(
    bind=True,
    max_retries=0,
    name="tasks.internet_check_tasks.check_internet_connectivity",
    queue="default",
)
def check_internet_connectivity(self) -> dict:
    """
    Periodic internet connectivity probe (runs every 60 s via celery beat).
    Caches result for 2 minutes so other tasks can read it cheaply.

    Side-effects:
      • Sets CONNECTIVITY_CACHE_KEY in Redis
      • Logs WARNING on transition online → offline
      • Triggers pause_outbound_tasks() when offline
      • Triggers resume_outbound_tasks() on recovery
    """
    # Debounce — don't run twice if beat fires slightly early
    if cache.get(CONNECTIVITY_LOCK_KEY):
        logger.debug("[InternetCheck] Debounce — skipping duplicate probe")
        return {"status": "skipped", "reason": "debounce"}
    cache.set(CONNECTIVITY_LOCK_KEY, 1, timeout=50)

    probe = _multi_probe_internet()

    prev = (cache.get(CONNECTIVITY_CACHE_KEY) or {}).get("online")

    cache.set(CONNECTIVITY_CACHE_KEY, probe, timeout=CONNECTIVITY_CACHE_TTL)

    if probe["online"]:
        logger.info(
            "[InternetCheck] ✅ ONLINE — latency=%sms passed=%d/%d",
            probe["latency_ms"], probe["passed"], len(PROBE_URLS),
        )
        if prev is False:
            # Recovered from offline — resume paused outbound tasks
            logger.info("[InternetCheck] 🔄 Recovery detected — resuming outbound tasks")
            resume_outbound_tasks.delay()
    else:
        logger.warning(
            "[InternetCheck] ❌ OFFLINE — passed=%d/%d details=%s",
            probe["passed"], len(PROBE_URLS), probe["details"],
        )
        if prev is not False:
            # Transition online → offline — pause outbound tasks
            logger.warning("[InternetCheck] ⏸ Connectivity lost — pausing outbound tasks")
            pause_outbound_tasks.delay()

    return {"status": "ok", "probe": probe}


def is_online(use_cache: bool = True) -> bool:
    """
    Synchronous helper — returns True if internet is available.
    Used by ConnectivityGate and task guards.
    """
    if use_cache:
        cached = cache.get(CONNECTIVITY_CACHE_KEY)
        if cached is not None:
            return cached.get("online", True)
    probe = _multi_probe_internet()
    cache.set(CONNECTIVITY_CACHE_KEY, probe, timeout=CONNECTIVITY_CACHE_TTL)
    return probe["online"]


def get_connectivity_status() -> dict:
    """Return cached connectivity status (cheap — no HTTP probe)."""
    cached = cache.get(CONNECTIVITY_CACHE_KEY)
    if cached:
        return cached
    # Cache miss → probe now
    probe = _multi_probe_internet()
    cache.set(CONNECTIVITY_CACHE_KEY, probe, timeout=CONNECTIVITY_CACHE_TTL)
    return probe


@shared_task(name="tasks.internet_check_tasks.pause_outbound_tasks", queue="high")
def pause_outbound_tasks() -> dict:
    """
    Sets a 'paused' flag in Redis that ConnectivityGate reads.
    Does NOT kill in-flight tasks — only prevents new ones from starting.
    Auto-expires after 10 minutes (safety valve).
    """
    cache.set("outbound_tasks_paused", True, timeout=600)
    logger.warning("[InternetCheck] ⏸ Outbound tasks PAUSED")
    return {"status": "paused"}


@shared_task(name="tasks.internet_check_tasks.resume_outbound_tasks", queue="high")
def resume_outbound_tasks() -> dict:
    """Clears the paused flag and re-queues tasks that were deferred."""
    cache.delete("outbound_tasks_paused")
    logger.info("[InternetCheck] ▶ Outbound tasks RESUMED")

    # Re-queue any tasks that were stored in the deferred queue
    deferred_key = "deferred_task_queue"
    deferred = cache.get(deferred_key) or []
    requeued = 0
    for task_spec in deferred:
        try:
            from celery import current_app
            current_app.send_task(task_spec["name"], args=task_spec.get("args", []),
                                  kwargs=task_spec.get("kwargs", {}),
                                  queue=task_spec.get("queue", "default"))
            requeued += 1
        except Exception as e:
            logger.error("[InternetCheck] Re-queue failed: %s", e)
    if deferred:
        cache.delete(deferred_key)
    logger.info("[InternetCheck] Re-queued %d deferred tasks", requeued)
    return {"status": "resumed", "requeued": requeued}


def are_outbound_tasks_paused() -> bool:
    return bool(cache.get("outbound_tasks_paused"))


def queue_when_online(task_name: str, args: list = None, kwargs: dict = None,
                      queue: str = "default") -> bool:
    """
    If currently offline, stores task_spec in Redis deferred queue instead
    of firing immediately. Returns True if deferred, False if sent normally.
    """
    if not are_outbound_tasks_paused():
        return False  # online — caller should send normally

    deferred_key = "deferred_task_queue"
    deferred = cache.get(deferred_key) or []
    deferred.append({"name": task_name, "args": args or [], "kwargs": kwargs or {},
                     "queue": queue})
    cache.set(deferred_key, deferred, timeout=3600)
    logger.info("[InternetCheck] Deferred %s (offline)", task_name)
    return True


class ConnectivityGate:
    """
    Decorator that skips a task body when the server is offline.
    Usage:
        @shared_task(bind=True)
        @ConnectivityGate()
        def my_outbound_task(self, ...):
            ...
    """
    def __init__(self, defer: bool = True):
        """
        defer=True  → store in deferred queue for retry on recovery
        defer=False → simply skip + log
        """
        self.defer = defer

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            if not is_online():
                logger.warning(
                    "[ConnectivityGate] OFFLINE — skipping %s", func.__name__
                )
                if self.defer:
                    queue_when_online(f"tasks.{func.__name__}", args=list(args[1:]),
                                      kwargs=kwargs)
                return {"status": "skipped", "reason": "offline"}
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__  = func.__doc__
        return wrapper


# ══════════════════════════════════════════════════════════════════════════════
# 2. AGING TASK DETECTION + AUTO-RECOVERY
# ══════════════════════════════════════════════════════════════════════════════

def _get_aging_started(threshold_minutes: int):
    from api.tasks.models import UserTaskCompletion
    cutoff = timezone.now() - timedelta(minutes=threshold_minutes)
    return UserTaskCompletion.objects.filter(
        status="started",
        started_at__lt=cutoff,
    ).select_related("task", "user")


def _get_aging_pending(threshold_hours: int):
    from api.tasks.models import UserTaskCompletion
    cutoff = timezone.now() - timedelta(hours=threshold_hours)
    return UserTaskCompletion.objects.filter(
        status="pending",
        started_at__lt=cutoff,
    ).select_related("task", "user")


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="tasks.internet_check_tasks.detect_aging_tasks",
    queue="default",
)
def detect_aging_tasks(self,
                       started_threshold_minutes: int = AGING_STARTED_THRESHOLD_MINUTES,
                       pending_threshold_hours:   int = AGING_PENDING_THRESHOLD_HOURS) -> dict:
    """
    Periodic scan (runs every 5 min via beat) to detect tasks that have
    been in 'started' or 'pending' status longer than expected.

    Returns a structured report cached for 10 minutes.
    Does NOT mutate any records — use auto_recover_aging_tasks() for that.
    """
    try:
        aging_started = list(_get_aging_started(started_threshold_minutes))
        aging_pending = list(_get_aging_pending(pending_threshold_hours))

        started_ids = [str(c.id) for c in aging_started]
        pending_ids = [str(c.id) for c in aging_pending]

        # Per-task breakdown for dashboard
        def _summarise(completions):
            return [
                {
                    "completion_id": str(c.id),
                    "task_id":       str(c.task_id),
                    "task_title":    str(c.task),
                    "user_id":       c.user_id,
                    "status":        c.status,
                    "age_minutes":   int(
                        (timezone.now() - c.started_at).total_seconds() / 60
                    ),
                    "platform":      getattr(c.task, "network_type", "unknown"),
                }
                for c in completions
            ]

        report = {
            "aging_started_count": len(aging_started),
            "aging_pending_count": len(aging_pending),
            "aging_started_ids":   started_ids[:50],   # cap for cache size
            "aging_pending_ids":   pending_ids[:50],
            "started_detail":      _summarise(aging_started[:20]),
            "pending_detail":      _summarise(aging_pending[:20]),
            "thresholds": {
                "started_minutes": started_threshold_minutes,
                "pending_hours":   pending_threshold_hours,
            },
            "detected_at": timezone.now().isoformat(),
        }

        cache.set("aging_task_report", report, timeout=600)

        total = len(aging_started) + len(aging_pending)
        level = "CRITICAL" if total > 50 else "WARNING" if total > 10 else "INFO"
        logger.log(
            logging.CRITICAL if level == "CRITICAL" else
            logging.WARNING  if level == "WARNING"  else logging.INFO,
            "[AgingTasks] %s: %d started-aging + %d pending-aging tasks",
            level, len(aging_started), len(aging_pending),
        )

        return {"status": "ok", "report": report}

    except Exception as exc:
        logger.error("[AgingTasks] detect_aging_tasks error: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name="tasks.internet_check_tasks.auto_recover_aging_tasks",
    queue="default",
)
def auto_recover_aging_tasks(self,
                              threshold_minutes: int = AGING_AUTO_RECOVER_THRESHOLD_MIN,
                              dry_run: bool = False) -> dict:
    """
    Auto-recovery for tasks that have been 'started' past threshold_minutes.
    Actions per aging task:
      1. Mark completion as 'failed' with reason 'aging_timeout'
      2. Release any held TaskLock
      3. Release TaskInventory slot (refund)
      4. Log TaskEventLog entry
      5. Notify user (via messaging adapter)
    dry_run=True → log what would happen without mutating records.
    """
    try:
        from django.db import transaction as db_tx
        from api.tasks.models import UserTaskCompletion, TaskLock, TaskEventLog

        aging = list(_get_aging_started(threshold_minutes))

        recovered = []
        skipped   = []
        errors    = []

        for completion in aging:
            try:
                if dry_run:
                    skipped.append({
                        "completion_id": str(completion.id),
                        "age_minutes": int(
                            (timezone.now() - completion.started_at).total_seconds() / 60
                        ),
                        "action": "would_recover",
                    })
                    continue

                with db_tx.atomic():
                    # 1. Mark failed
                    completion.status = "failed"
                    completion.save(update_fields=["status"])

                    # 2. Release TaskLock
                    TaskLock.objects.filter(
                        task=completion.task,
                        user=completion.user,
                        released_at__isnull=True,
                    ).update(
                        released_at=timezone.now(),
                        lock_holder_worker="aging_recovery",
                    )

                    # 3. Refund inventory slot
                    try:
                        from api.tasks.api.adapters.inventory import release_slot
                        payout = getattr(completion, "reward_amount", Decimal("0")) or Decimal("0")
                        release_slot(completion.task_id, payout_usd=payout)
                    except Exception as inv_err:
                        logger.warning("[AgingRecovery] Inventory release failed: %s", inv_err)

                    # 4. Audit log
                    TaskEventLog.objects.create(
                        event_type="AGING_RECOVERY",
                        task=completion.task,
                        user=completion.user,
                        actor_type="SYSTEM",
                        event_data={
                            "completion_id": str(completion.id),
                            "age_minutes": int(
                                (timezone.now() - completion.started_at).total_seconds() / 60
                            ),
                            "threshold_minutes": threshold_minutes,
                            "action": "auto_failed",
                        },
                    )

                # 5. Notify user
                try:
                    from api.tasks.api.adapters.messaging import send
                    send(
                        user_id=completion.user_id,
                        message=(
                            f"Your task '{completion.task}' timed out and was automatically "
                            f"cancelled after {threshold_minutes} minutes. "
                            f"You can retry the task."
                        ),
                        channel="in_app",
                        title="Task Timed Out",
                    )
                except Exception as msg_err:
                    logger.warning("[AgingRecovery] Notification failed: %s", msg_err)

                recovered.append({"completion_id": str(completion.id), "task_id": str(completion.task_id)})

            except Exception as item_err:
                logger.error("[AgingRecovery] Failed to recover %s: %s", completion.id, item_err)
                errors.append({"completion_id": str(completion.id), "error": str(item_err)})

        result = {
            "status":     "dry_run" if dry_run else "ok",
            "found":      len(aging),
            "recovered":  len(recovered),
            "skipped":    len(skipped),
            "errors":     len(errors),
            "details":    recovered[:20],
            "error_list": errors[:10],
            "threshold_minutes": threshold_minutes,
            "ran_at": timezone.now().isoformat(),
        }

        cache.set("aging_recovery_last_run", result, timeout=3600)
        logger.info(
            "[AgingRecovery] found=%d recovered=%d errors=%d dry_run=%s",
            len(aging), len(recovered), len(errors), dry_run,
        )
        return result

    except Exception as exc:
        logger.error("[AgingRecovery] auto_recover_aging_tasks error: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    name="tasks.internet_check_tasks.aging_report",
    queue="default",
)
def aging_report() -> dict:
    """Return cached aging report (cheap — no DB query if cache warm)."""
    report = cache.get("aging_task_report")
    if report:
        return {"status": "cached", "report": report}

    # Cache miss — run detection inline (synchronous, no retry)
    from api.tasks.models import UserTaskCompletion

    aging_started = _get_aging_started(AGING_STARTED_THRESHOLD_MINUTES)
    aging_pending = _get_aging_pending(AGING_PENDING_THRESHOLD_HOURS)

    return {
        "status": "live",
        "aging_started_count": aging_started.count(),
        "aging_pending_count": aging_pending.count(),
        "generated_at": timezone.now().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. LOCK AGING — stale exclusive locks
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="tasks.internet_check_tasks.expire_stale_task_locks",
    queue="default",
)
def expire_stale_task_locks(self,
                             threshold_minutes: int = LOCK_STALE_THRESHOLD_MINUTES,
                             dry_run: bool = False) -> dict:
    """
    Periodic scan (every 5 min via beat) — finds TaskLock rows that:
      • are not released (released_at IS NULL)
      • have expires_at < NOW()  OR  acquired_at + threshold < NOW()
    Releases them by setting released_at = NOW().
    """
    try:
        from api.tasks.models import TaskLock, TaskEventLog

        cutoff_time = timezone.now() - timedelta(minutes=threshold_minutes)

        # Build Q for OR condition
        from django.db.models import Q
        stale_locks = TaskLock.objects.filter(
            released_at__isnull=True,
        ).filter(
            Q(expires_at__lt=timezone.now()) |
            Q(acquired_at__lt=cutoff_time)
        ).select_related("task", "user")

        count   = stale_locks.count()
        details = []

        if dry_run:
            for lock in stale_locks[:50]:
                details.append({
                    "lock_id":  str(lock.id),
                    "task_id":  str(lock.task_id),
                    "user_id":  lock.user_id,
                    "held_min": int(
                        (timezone.now() - lock.acquired_at).total_seconds() / 60
                    ),
                    "action": "would_release",
                })
        else:
            for lock in stale_locks[:200]:
                try:
                    held_min = int(
                        (timezone.now() - lock.acquired_at).total_seconds() / 60
                    )
                    lock.released_at = timezone.now()
                    lock.lock_holder_worker = "expire_stale_locks"
                    lock.save(update_fields=["released_at", "lock_holder_worker"])

                    TaskEventLog.objects.create(
                        event_type="LOCK_FORCE_RELEASED",
                        task=lock.task,
                        user=lock.user,
                        actor_type="SYSTEM",
                        event_data={
                            "lock_id": str(lock.id),
                            "held_minutes": held_min,
                            "reason": "stale_threshold_exceeded",
                            "threshold_minutes": threshold_minutes,
                        },
                    )
                    details.append({"lock_id": str(lock.id), "held_min": held_min})
                except Exception as le:
                    logger.error("[LockAging] Failed to release lock %s: %s", lock.id, le)

        result = {
            "status":    "dry_run" if dry_run else "ok",
            "found":     count,
            "released":  0 if dry_run else len(details),
            "details":   details[:20],
            "threshold_minutes": threshold_minutes,
            "ran_at":    timezone.now().isoformat(),
        }

        logger.info(
            "[LockAging] found=%d released=%d dry_run=%s",
            count, 0 if dry_run else len(details), dry_run,
        )
        return result

    except Exception as exc:
        logger.error("[LockAging] expire_stale_task_locks error: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    name="tasks.internet_check_tasks.force_release_stuck_lock",
    queue="high",
)
def force_release_stuck_lock(lock_id: str, reason: str = "admin_forced") -> dict:
    """
    Admin-triggered hard release of a specific TaskLock.
    Callable from admin dashboard or management command.
    """
    try:
        from api.tasks.models import TaskLock, TaskEventLog

        lock = TaskLock.objects.select_for_update().get(pk=lock_id)

        if lock.released_at:
            return {"status": "already_released", "lock_id": lock_id}

        lock.released_at = timezone.now()
        lock.lock_holder_worker = reason
        lock.save(update_fields=["released_at", "lock_holder_worker"])

        TaskEventLog.objects.create(
            event_type="LOCK_FORCE_RELEASED",
            task=lock.task,
            user=lock.user,
            actor_type="ADMIN",
            event_data={"lock_id": lock_id, "reason": reason},
        )

        logger.info("[LockAging] Force-released lock %s — reason: %s", lock_id, reason)
        return {"status": "released", "lock_id": lock_id, "reason": reason}

    except Exception as e:
        logger.error("[LockAging] force_release_stuck_lock error: %s", e)
        return {"status": "error", "error": str(e)}
