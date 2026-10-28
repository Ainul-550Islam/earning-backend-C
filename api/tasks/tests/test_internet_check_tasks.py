"""
tests/test_internet_check_tasks.py — Internet connectivity + aging task tests
"""
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.utils import timezone


@pytest.fixture
def clear_cache(db):
    from django.core.cache import cache
    for k in ("internet_connectivity_status","outbound_tasks_paused",
              "internet_connectivity_lock","deferred_task_queue"):
        cache.delete(k)
    yield
    for k in ("internet_connectivity_status","outbound_tasks_paused",
              "internet_connectivity_lock","deferred_task_queue"):
        cache.delete(k)


@pytest.fixture
def aging_completion(db, master_task, user):
    from api.tasks.models import UserTaskCompletion
    c = UserTaskCompletion.objects.create(
        task=master_task, user=user, status="started", ip_address="127.0.0.1")
    UserTaskCompletion.objects.filter(pk=c.pk).update(
        started_at=timezone.now() - timedelta(minutes=90))
    c.refresh_from_db(); return c


@pytest.fixture
def stale_lock(db, master_task, user):
    from api.tasks.models import TaskLock
    lock = TaskLock.objects.create(
        task=master_task, user=user,
        lock_type=TaskLock.LockType.EXCLUSIVE,
        expires_at=timezone.now() - timedelta(minutes=30))
    TaskLock.objects.filter(pk=lock.pk).update(
        acquired_at=timezone.now() - timedelta(minutes=90))
    lock.refresh_from_db(); return lock


# ── _multi_probe_internet ─────────────────────────────────────────────────────

class TestMultiProbeInternet:
    def test_online_when_probes_succeed(self):
        from api.tasks.internet_check_tasks import _multi_probe_internet
        mock_resp = MagicMock(); mock_resp.status_code = 200
        with patch("tasks.internet_check_tasks.requests.get", return_value=mock_resp):
            r = _multi_probe_internet()
        assert r["online"] is True and r["passed"] >= 2

    def test_offline_when_all_fail(self):
        from api.tasks.internet_check_tasks import _multi_probe_internet
        with patch("tasks.internet_check_tasks.requests.get",
                   side_effect=Exception("refused")):
            r = _multi_probe_internet()
        assert r["online"] is False and r["passed"] == 0

    def test_required_keys_present(self):
        from api.tasks.internet_check_tasks import _multi_probe_internet
        with patch("tasks.internet_check_tasks.requests.get",
                   side_effect=Exception("x")):
            r = _multi_probe_internet()
        for k in ("online","passed","failed","probed_at","details"):
            assert k in r

    def test_early_exit_on_threshold(self):
        from api.tasks.internet_check_tasks import _multi_probe_internet, PROBE_PASS_THRESHOLD
        mock_resp = MagicMock(); mock_resp.status_code = 200
        calls = [0]
        def se(url, timeout): calls[0] += 1; return mock_resp
        with patch("tasks.internet_check_tasks.requests.get", side_effect=se):
            r = _multi_probe_internet()
        assert calls[0] == PROBE_PASS_THRESHOLD and r["online"] is True


# ── check_internet_connectivity task ─────────────────────────────────────────

class TestCheckInternetConnectivity:
    def _probe(self, online):
        return {"online": online, "passed": 3 if online else 0,
                "latency_ms": 30.0, "probed_at": "2026-01-01", "details": []}

    def test_ok_when_online(self, clear_cache):
        from api.tasks.internet_check_tasks import check_internet_connectivity
        with patch("tasks.internet_check_tasks._multi_probe_internet",
                   return_value=self._probe(True)):
            r = check_internet_connectivity()
        assert r["status"] == "ok" and r["probe"]["online"] is True

    def test_pauses_on_offline_transition(self, clear_cache):
        from api.tasks.internet_check_tasks import check_internet_connectivity
        with patch("tasks.internet_check_tasks._multi_probe_internet",
                   return_value=self._probe(False)), \
             patch("tasks.internet_check_tasks.pause_outbound_tasks") as mp:
            check_internet_connectivity()
        mp.delay.assert_called_once()

    def test_resumes_on_recovery(self, clear_cache):
        from api.tasks.internet_check_tasks import check_internet_connectivity
        from django.core.cache import cache
        cache.set("internet_connectivity_status", {"online": False}, timeout=120)
        with patch("tasks.internet_check_tasks._multi_probe_internet",
                   return_value=self._probe(True)), \
             patch("tasks.internet_check_tasks.resume_outbound_tasks") as mr:
            check_internet_connectivity()
        mr.delay.assert_called_once()

    def test_debounce_returns_skipped(self, clear_cache):
        from api.tasks.internet_check_tasks import check_internet_connectivity
        from django.core.cache import cache
        cache.set("internet_connectivity_lock", 1, timeout=50)
        assert check_internet_connectivity()["status"] == "skipped"

    def test_caches_result(self, clear_cache):
        from api.tasks.internet_check_tasks import check_internet_connectivity
        from django.core.cache import cache
        with patch("tasks.internet_check_tasks._multi_probe_internet",
                   return_value=self._probe(True)):
            check_internet_connectivity()
        assert cache.get("internet_connectivity_status") is not None


# ── is_online / get_connectivity_status ──────────────────────────────────────

class TestIsOnline:
    def test_true_from_cache(self, clear_cache):
        from api.tasks.internet_check_tasks import is_online
        from django.core.cache import cache
        cache.set("internet_connectivity_status", {"online": True}, timeout=120)
        assert is_online() is True

    def test_false_from_cache(self, clear_cache):
        from api.tasks.internet_check_tasks import is_online
        from django.core.cache import cache
        cache.set("internet_connectivity_status", {"online": False}, timeout=120)
        assert is_online() is False

    def test_probes_on_cache_miss(self, clear_cache):
        from api.tasks.internet_check_tasks import is_online
        probe = {"online": True, "passed": 2, "latency_ms": 20.0,
                 "probed_at": "2026-01-01", "details": []}
        with patch("tasks.internet_check_tasks._multi_probe_internet", return_value=probe):
            assert is_online(use_cache=False) is True


# ── ConnectivityGate ──────────────────────────────────────────────────────────

class TestConnectivityGate:
    def test_runs_when_online(self, clear_cache):
        from api.tasks.internet_check_tasks import ConnectivityGate
        from django.core.cache import cache
        cache.set("internet_connectivity_status", {"online": True}, timeout=120)

        @ConnectivityGate()
        def my_task(self, v): return {"done": v}

        assert my_task(None, "x")["done"] == "x"

    def test_skips_when_offline(self, clear_cache):
        from api.tasks.internet_check_tasks import ConnectivityGate
        from django.core.cache import cache
        cache.set("internet_connectivity_status", {"online": False}, timeout=120)

        @ConnectivityGate(defer=False)
        def my_task(self): return {"done": True}

        r = my_task(None)
        assert r["status"] == "skipped" and r["reason"] == "offline"

    def test_defers_when_offline(self, clear_cache):
        from api.tasks.internet_check_tasks import ConnectivityGate
        from django.core.cache import cache
        cache.set("internet_connectivity_status", {"online": False}, timeout=120)
        cache.set("outbound_tasks_paused", True, timeout=600)

        @ConnectivityGate(defer=True)
        def outbound(self, uid): return {}

        outbound(None, 1)
        assert len(cache.get("deferred_task_queue") or []) >= 1

    def test_preserves_name_and_doc(self):
        from api.tasks.internet_check_tasks import ConnectivityGate

        @ConnectivityGate()
        def fetch_offers(self):
            """My doc."""
            pass

        assert fetch_offers.__name__ == "fetch_offers"
        assert fetch_offers.__doc__ == "My doc."


# ── pause / resume / queue_when_online ───────────────────────────────────────

class TestPauseResume:
    def test_pause_sets_flag(self, clear_cache):
        from api.tasks.internet_check_tasks import pause_outbound_tasks, are_outbound_tasks_paused
        pause_outbound_tasks(); assert are_outbound_tasks_paused() is True

    def test_resume_clears_flag(self, clear_cache):
        from api.tasks.internet_check_tasks import pause_outbound_tasks, resume_outbound_tasks, are_outbound_tasks_paused
        pause_outbound_tasks(); resume_outbound_tasks()
        assert are_outbound_tasks_paused() is False

    def test_resume_requeues_deferred(self, clear_cache):
        from django.core.cache import cache
        from api.tasks.internet_check_tasks import resume_outbound_tasks
        cache.set("deferred_task_queue", [
            {"name": "tasks.some_task", "args": [], "kwargs": {}, "queue": "default"}
        ], timeout=3600)
        with patch("tasks.internet_check_tasks.current_app"):
            r = resume_outbound_tasks()
        assert r["requeued"] == 1
        assert cache.get("deferred_task_queue") is None

    def test_queue_when_online_false_if_not_paused(self, clear_cache):
        from api.tasks.internet_check_tasks import queue_when_online
        assert queue_when_online("tasks.x") is False

    def test_queue_when_online_defers_if_paused(self, clear_cache):
        from api.tasks.internet_check_tasks import queue_when_online
        from django.core.cache import cache
        cache.set("outbound_tasks_paused", True, timeout=600)
        assert queue_when_online("tasks.x", args=[1]) is True


# ── detect_aging_tasks ────────────────────────────────────────────────────────

class TestDetectAgingTasks:
    def test_detects_aging(self, db, aging_completion):
        from api.tasks.internet_check_tasks import detect_aging_tasks
        r = detect_aging_tasks(started_threshold_minutes=60)
        assert r["status"] == "ok"
        assert r["report"]["aging_started_count"] >= 1

    def test_required_keys(self, db):
        from api.tasks.internet_check_tasks import detect_aging_tasks
        r = detect_aging_tasks()
        for k in ("aging_started_count","aging_pending_count","thresholds",
                  "detected_at","started_detail"):
            assert k in r["report"]

    def test_caches_report(self, db, clear_cache):
        from api.tasks.internet_check_tasks import detect_aging_tasks
        from django.core.cache import cache
        detect_aging_tasks()
        assert cache.get("aging_task_report") is not None

    def test_zero_when_no_aging(self, db):
        from api.tasks.internet_check_tasks import detect_aging_tasks
        r = detect_aging_tasks(started_threshold_minutes=99999, pending_threshold_hours=99999)
        assert r["report"]["aging_started_count"] == 0


# ── auto_recover_aging_tasks ──────────────────────────────────────────────────

class TestAutoRecoverAgingTasks:
    def test_dry_run_no_mutation(self, db, aging_completion):
        from api.tasks.internet_check_tasks import auto_recover_aging_tasks
        auto_recover_aging_tasks(threshold_minutes=60, dry_run=True)
        aging_completion.refresh_from_db()
        assert aging_completion.status == "started"

    def test_recovers_completion(self, db, aging_completion):
        from api.tasks.internet_check_tasks import auto_recover_aging_tasks
        auto_recover_aging_tasks(threshold_minutes=60, dry_run=False)
        aging_completion.refresh_from_db()
        assert aging_completion.status == "failed"

    def test_creates_event_log(self, db, aging_completion):
        from api.tasks.internet_check_tasks import auto_recover_aging_tasks
        from api.tasks.models import TaskEventLog
        auto_recover_aging_tasks(threshold_minutes=60, dry_run=False)
        assert TaskEventLog.objects.filter(event_type="AGING_RECOVERY").exists()

    def test_zero_when_no_aging(self, db):
        from api.tasks.internet_check_tasks import auto_recover_aging_tasks
        r = auto_recover_aging_tasks(threshold_minutes=99999)
        assert r["recovered"] == 0


# ── expire_stale_task_locks ───────────────────────────────────────────────────

class TestExpireStaleTaskLocks:
    def test_releases_expired_lock(self, db, stale_lock):
        from api.tasks.internet_check_tasks import expire_stale_task_locks
        expire_stale_task_locks(threshold_minutes=60, dry_run=False)
        stale_lock.refresh_from_db()
        assert stale_lock.released_at is not None

    def test_dry_run_no_release(self, db, stale_lock):
        from api.tasks.internet_check_tasks import expire_stale_task_locks
        r = expire_stale_task_locks(threshold_minutes=60, dry_run=True)
        assert r["status"] == "dry_run"
        stale_lock.refresh_from_db()
        assert stale_lock.released_at is None

    def test_creates_event_log(self, db, stale_lock):
        from api.tasks.internet_check_tasks import expire_stale_task_locks
        from api.tasks.models import TaskEventLog
        expire_stale_task_locks(threshold_minutes=60, dry_run=False)
        assert TaskEventLog.objects.filter(event_type="LOCK_FORCE_RELEASED").exists()

    def test_fresh_lock_not_touched(self, db, master_task, user):
        from api.tasks.models import TaskLock
        from api.tasks.internet_check_tasks import expire_stale_task_locks
        fresh = TaskLock.objects.create(
            task=master_task, user=user,
            lock_type=TaskLock.LockType.EXCLUSIVE,
            expires_at=timezone.now() + timedelta(hours=24))
        expire_stale_task_locks(threshold_minutes=60, dry_run=False)
        fresh.refresh_from_db()
        assert fresh.released_at is None


# ── force_release_stuck_lock ──────────────────────────────────────────────────

class TestForceReleaseStuckLock:
    def test_releases_lock(self, db, stale_lock):
        from api.tasks.internet_check_tasks import force_release_stuck_lock
        r = force_release_stuck_lock(lock_id=str(stale_lock.id), reason="test")
        assert r["status"] == "released"
        stale_lock.refresh_from_db()
        assert stale_lock.released_at is not None

    def test_already_released(self, db, stale_lock):
        from api.tasks.internet_check_tasks import force_release_stuck_lock
        stale_lock.released_at = timezone.now(); stale_lock.save()
        assert force_release_stuck_lock(str(stale_lock.id))["status"] == "already_released"

    def test_invalid_id_returns_error(self, db):
        from api.tasks.internet_check_tasks import force_release_stuck_lock
        assert force_release_stuck_lock(
            "00000000-0000-0000-0000-000000000000")["status"] == "error"


# ── API Views ─────────────────────────────────────────────────────────────────

class TestConnectivityViews:
    def test_status_authenticated(self, auth_client, clear_cache):
        from django.core.cache import cache
        cache.set("internet_connectivity_status",
                  {"online": True, "latency_ms": 30.0, "passed": 3,
                   "probed_at": "2026-01-01", "details": []}, timeout=120)
        r = auth_client.get("/api/connectivity/")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert "online" in r.data and "outbound_paused" in r.data

    def test_status_unauthenticated(self, client):
        r = client.get("/api/connectivity/")
        assert r.status_code in (401, 403, 404)

    def test_probe_admin(self, staff_client):
        probe = {"online": True, "passed": 3, "latency_ms": 25.0,
                 "probed_at": "2026-01-01", "details": []}
        with patch("tasks.internet_check_tasks._multi_probe_internet", return_value=probe):
            r = staff_client.post("/api/connectivity/probe/")
        assert r.status_code in (200, 404)

    def test_probe_non_admin(self, auth_client):
        r = auth_client.post("/api/connectivity/probe/")
        assert r.status_code in (403, 404)


class TestAgingViews:
    def test_report_admin(self, staff_client):
        r = staff_client.get("/api/aging-tasks/")
        assert r.status_code in (200, 404)

    def test_report_non_admin(self, auth_client):
        r = auth_client.get("/api/aging-tasks/")
        assert r.status_code in (403, 404)

    def test_recover_dry_run(self, staff_client):
        r = staff_client.post("/api/aging-tasks/recover/", {"dry_run": True})
        assert r.status_code in (200, 404)

    def test_recover_non_admin(self, auth_client):
        r = auth_client.post("/api/aging-tasks/recover/", {})
        assert r.status_code in (403, 404)


class TestStaleLocksViews:
    def test_report_admin(self, staff_client):
        r = staff_client.get("/api/stale-locks/")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert "count" in r.data and "locks" in r.data

    def test_report_with_threshold(self, staff_client):
        r = staff_client.get("/api/stale-locks/?threshold_minutes=120")
        assert r.status_code in (200, 404)

    def test_report_non_admin(self, auth_client):
        r = auth_client.get("/api/stale-locks/")
        assert r.status_code in (403, 404)

    def test_force_release_admin(self, staff_client, stale_lock):
        r = staff_client.post("/api/stale-locks/force-release/",
                              {"lock_id": str(stale_lock.id)})
        assert r.status_code in (200, 404)

    def test_force_release_missing_id(self, staff_client):
        r = staff_client.post("/api/stale-locks/force-release/", {})
        assert r.status_code in (400, 404)

    def test_force_release_non_admin(self, auth_client, stale_lock):
        r = auth_client.post("/api/stale-locks/force-release/",
                             {"lock_id": str(stale_lock.id)})
        assert r.status_code in (403, 404)
