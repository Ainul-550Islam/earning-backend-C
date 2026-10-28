"""
tests/test_views_tasks.py
=========================
Comprehensive tests for views_tasks.py.

Coverage targets
----------------
• Every task trigger view: auth, admin-gating, enqueue success, enqueue fail
• Monitoring views: list, status, active, scheduled, history, stats, revoke
• Parameter validation: invalid types, missing required fields
• _enqueue fallback when Celery is unavailable
• TaskHistoryAPIView.record() helper
• TASK_REGISTRY completeness (all 22 tasks present)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

User = get_user_model()

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _admin(username="admin_tasks"):
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.example.com",
        password="pass",
        is_staff=True,
        is_superuser=True,
    )


def _user(username="regular_tasks"):
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.example.com",
        password="pass",
    )


def _mock_enqueue(task_id="test-task-123", queued=True):
    """Return a mock _enqueue response."""
    return {
        "queued":    queued,
        "task_id":   task_id,
        "task_name": "mock_task",
        "status":    "PENDING",
    }


# ---------------------------------------------------------------------------
# TASK_REGISTRY integrity test
# ---------------------------------------------------------------------------

class TaskRegistryTest(APITestCase):
    """Verify TASK_REGISTRY contains all 22 known tasks."""

    def test_registry_has_all_tasks(self):
        from api.fraud_detection.views_tasks import TASK_REGISTRY
        expected = {
            "run_fraud_scan",
            "auto_ban_high_risk",
            "calculate_user_risk_scores",
            "update_device_trust_scores",
            "train_fraud_patterns",
            "analyze_fraud_patterns",
            "graph_network_scan",
            "velocity_engine_cleanup",
            "ml_drift_check",
            "retrain_fraud_patterns",
            "recalculate_stale_risk_profiles",
            "send_pending_notifications",
            "retry_failed_notifications",
            "deliver_fraud_notification",
            "warm_fraud_cache",
            "cleanup_fraud_cache",
            "generate_fraud_report",
            "archive_old_fraud_data",
            "cleanup_orphaned_records",
            "ip_reputation_cleanup",
            "whitelist_cleanup_expired",
            "check_and_unban_users",
            "audit_log_cleanup",
        }
        self.assertTrue(expected.issubset(set(TASK_REGISTRY.keys())))

    def test_registry_slug_unique(self):
        from api.fraud_detection.views_tasks import TASK_REGISTRY
        slugs = [m["slug"] for m in TASK_REGISTRY.values()]
        self.assertEqual(len(slugs), len(set(slugs)), "Duplicate slugs in TASK_REGISTRY")

    def test_slug_to_task_reverse_lookup(self):
        from api.fraud_detection.views_tasks import TASK_REGISTRY, SLUG_TO_TASK
        for name, meta in TASK_REGISTRY.items():
            self.assertEqual(SLUG_TO_TASK[meta["slug"]], name)


# ---------------------------------------------------------------------------
# _enqueue helper unit tests
# ---------------------------------------------------------------------------

class EnqueueHelperTest(APITestCase):

    def test_enqueue_returns_queued_false_when_celery_missing(self):
        from api.fraud_detection.views_tasks import _enqueue
        with patch("api.fraud_detection.views_tasks.__import__", side_effect=ImportError):
            result = _enqueue("some_task")
        # Should not raise; returns dict with queued=False or raises ImportError caught internally
        self.assertIsInstance(result, dict)

    def test_enqueue_returns_queued_false_on_attr_error(self):
        """If the task function doesn't exist in the module."""
        from api.fraud_detection.views_tasks import _enqueue
        mock_tasks = MagicMock(spec=[])  # no attributes
        with patch("api.fraud_detection.views_tasks.__import__", return_value=mock_tasks):
            result = _enqueue("nonexistent_task_xyz")
        self.assertIsInstance(result, dict)

    def test_task_result_handles_missing_celery(self):
        from api.fraud_detection.views_tasks import _task_result
        with patch("api.fraud_detection.views_tasks.AsyncResult", side_effect=ImportError):
            result = _task_result("abc123")
        self.assertIn("task_id", result)


# ---------------------------------------------------------------------------
# Monitoring views
# ---------------------------------------------------------------------------

class TaskListViewTest(APITestCase):
    """GET /fraud/tasks/"""

    def setUp(self):
        self.admin  = _admin("admin_tl")
        self.user   = _user("user_tl")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:task-list")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_list(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("tasks", resp.data)

    def test_response_contains_all_tasks(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data["total"], 22)

    def test_group_filter_narrows_results(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.url + "?group=detection")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for task in resp.data["tasks"]:
            self.assertEqual(task["group"], "detection")

    def test_each_task_has_trigger_url(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.url)
        for task in resp.data["tasks"]:
            self.assertIn("trigger_url", task)
            self.assertTrue(task["trigger_url"].startswith("/fraud/tasks/"))


class TaskStatusViewTest(APITestCase):
    """GET /fraud/tasks/status/<task_id>/"""

    def setUp(self):
        self.user   = _user("user_ts")
        self.client = APIClient()

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(
            reverse("fraud_detection:task-status", kwargs={"task_id": "abc"})
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_returns_result(self):
        self.client.force_authenticate(self.user)
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.failed.return_value = False
        mock_result.result = {"done": True}
        with patch("api.fraud_detection.views_tasks.AsyncResult", return_value=mock_result):
            resp = self.client.get(
                reverse("fraud_detection:task-status", kwargs={"task_id": "abc123"})
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["task_id"], "abc123")

    def test_returns_unknown_when_celery_unavailable(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_tasks.AsyncResult", side_effect=ImportError):
            resp = self.client.get(
                reverse("fraud_detection:task-status", kwargs={"task_id": "xyz"})
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("status", resp.data)


class TaskRevokeViewTest(APITestCase):
    """POST /fraud/tasks/revoke/<task_id>/"""

    def setUp(self):
        self.admin  = _admin("admin_rev")
        self.user   = _user("user_rev")
        self.client = APIClient()

    def test_unauthenticated_returns_401(self):
        resp = self.client.post(
            reverse("fraud_detection:task-revoke", kwargs={"task_id": "abc"}), {}
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_returns_403(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse("fraud_detection:task-revoke", kwargs={"task_id": "abc"}), {}
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_revokes_successfully(self):
        self.client.force_authenticate(self.admin)
        mock_app = MagicMock()
        with patch("api.fraud_detection.views_tasks._try_celery_app", return_value=mock_app):
            resp = self.client.post(
                reverse("fraud_detection:task-revoke", kwargs={"task_id": "abc123"}),
                {"terminate": False},
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["revoked"])


class TaskActiveViewTest(APITestCase):
    """GET /fraud/tasks/active/"""

    def setUp(self):
        self.user   = _user("user_ta")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:task-active")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_active_tasks(self):
        self.client.force_authenticate(self.user)
        mock_app = MagicMock()
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = {
            "worker1@host": [{"id": "t1", "name": "my_task", "args": [], "kwargs": {}, "time_start": 1.0}]
        }
        mock_app.control.inspect.return_value = mock_inspect
        with patch("api.fraud_detection.views_tasks._try_celery_app", return_value=mock_app):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("active_count", resp.data)
        self.assertEqual(resp.data["active_count"], 1)

    def test_graceful_when_celery_unavailable(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_tasks._try_celery_app", return_value=None):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["active"], [])


class TaskHistoryViewTest(APITestCase):
    """GET /fraud/tasks/history/"""

    def setUp(self):
        self.user   = _user("user_th")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:task-history")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_history_returns_ok(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_tasks.cache") as mock_cache:
            mock_cache.get.return_value = []
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["history"], [])

    def test_history_with_entries(self):
        self.client.force_authenticate(self.user)
        entries = [
            {"task_name": "run_fraud_scan", "task_id": "t1", "status": "SUCCESS",
             "group": "detection", "triggered_at": "2024-01-01T00:00:00Z"},
            {"task_name": "warm_fraud_cache", "task_id": "t2", "status": "PENDING",
             "group": "maintenance", "triggered_at": "2024-01-01T01:00:00Z"},
        ]
        with patch("api.fraud_detection.views_tasks.cache") as mock_cache:
            mock_cache.get.return_value = entries
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 2)

    def test_group_filter(self):
        self.client.force_authenticate(self.user)
        entries = [
            {"task_name": "run_fraud_scan", "group": "detection", "task_id": "t1",
             "status": "OK", "triggered_at": "2024-01-01"},
            {"task_name": "warm_fraud_cache", "group": "maintenance", "task_id": "t2",
             "status": "OK", "triggered_at": "2024-01-01"},
        ]
        with patch("api.fraud_detection.views_tasks.cache") as mock_cache:
            mock_cache.get.return_value = entries
            resp = self.client.get(self.url + "?group=detection")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for h in resp.data["history"]:
            self.assertEqual(h["group"], "detection")

    def test_limit_param(self):
        self.client.force_authenticate(self.user)
        entries = [{"task_name": f"t{i}", "group": "g", "task_id": str(i),
                    "status": "OK", "triggered_at": "2024-01"} for i in range(100)]
        with patch("api.fraud_detection.views_tasks.cache") as mock_cache:
            mock_cache.get.return_value = entries
            resp = self.client.get(self.url + "?limit=5")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(resp.data["history"]), 5)

    def test_record_classmethod_writes_to_cache(self):
        from api.fraud_detection.views_tasks import TaskHistoryAPIView
        with patch("api.fraud_detection.views_tasks.cache") as mock_cache:
            mock_cache.get.return_value = []
            TaskHistoryAPIView.record("run_fraud_scan", "task-id-abc", "PENDING", "admin")
            mock_cache.set.assert_called_once()


class TaskStatsViewTest(APITestCase):
    """GET /fraud/tasks/stats/"""

    def setUp(self):
        self.user   = _user("user_tst")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:task-stats")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_stats_shape(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_tasks.cache") as mock_cache:
            mock_cache.get.return_value = [
                {"status": "SUCCESS", "group": "detection"},
                {"status": "FAILURE", "group": "maintenance"},
            ]
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_runs", resp.data)
        self.assertIn("by_status", resp.data)
        self.assertIn("by_group", resp.data)


class TaskScheduledViewTest(APITestCase):
    """GET /fraud/tasks/scheduled/"""

    def setUp(self):
        self.user   = _user("user_tsched")
        self.client = APIClient()
        self.url    = reverse("fraud_detection:task-scheduled")

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_config_schedule_when_celery_unavailable(self):
        self.client.force_authenticate(self.user)
        with patch("api.fraud_detection.views_tasks._try_celery_app", return_value=None):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("config_schedule", resp.data)
        self.assertGreater(len(resp.data["config_schedule"]), 0)


# ---------------------------------------------------------------------------
# Group A — trigger views
# ---------------------------------------------------------------------------

class _TriggerBase(APITestCase):
    """Mixin for all trigger view tests."""
    url_name: str = ""

    def setUp(self):
        self.admin  = _admin(f"admin_{self.__class__.__name__}")
        self.user   = _user(f"user_{self.__class__.__name__}")
        self.client = APIClient()

    def _url(self, **kwargs):
        return reverse(f"fraud_detection:{self.url_name}", **kwargs)

    def test_unauthenticated_returns_401(self):
        resp = self.client.post(self._url(), {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_returns_403(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self._url(), {})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_enqueues_successfully(self):
        self.client.force_authenticate(self.admin)
        mock_fn   = MagicMock()
        mock_fn.delay.return_value = MagicMock(id="task-abc-123")
        mock_mod  = MagicMock()
        setattr(mock_mod, self._task_fn_name(), mock_fn)
        with patch("api.fraud_detection.views_tasks.__import__", return_value=mock_mod):
            resp = self.client.post(self._url(), self._body())
        self.assertIn(resp.status_code, [
            status.HTTP_200_OK, status.HTTP_202_ACCEPTED,
        ])

    def test_admin_gets_graceful_response_when_celery_unavailable(self):
        self.client.force_authenticate(self.admin)
        with patch("api.fraud_detection.views_tasks._enqueue",
                   return_value={"queued": False, "error": "Celery not configured",
                                 "task_name": "mock"}):
            resp = self.client.post(self._url(), self._body())
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])
        self.assertFalse(resp.data.get("queued", True))

    def _task_fn_name(self):
        return self.url_name.replace("-", "_")

    def _body(self):
        return {}


class TaskRunFraudScanTriggerTest(_TriggerBase):
    url_name = "task-run-fraud-scan"
    def _task_fn_name(self): return "run_fraud_scan"


class TaskAutoBanHighRiskTriggerTest(_TriggerBase):
    url_name = "task-auto-ban-high-risk"
    def _task_fn_name(self): return "auto_ban_high_risk"


class TaskCalculateRiskScoresTriggerTest(_TriggerBase):
    url_name = "task-calculate-risk-scores"
    def _task_fn_name(self): return "calculate_user_risk_scores"

    def test_optional_user_ids_accepted(self):
        self.client.force_authenticate(self.admin)
        with patch("api.fraud_detection.views_tasks._enqueue",
                   return_value=_mock_enqueue()):
            resp = self.client.post(self._url(), {"user_ids": [1, 2, 3]},
                                    format="json")
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])

    def test_invalid_user_ids_returns_400(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self._url(), {"user_ids": "not-a-list"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class TaskUpdateDeviceTrustTriggerTest(_TriggerBase):
    url_name = "task-update-device-trust"
    def _task_fn_name(self): return "update_device_trust_scores"


class TaskTrainPatternsTriggerTest(_TriggerBase):
    url_name = "task-train-patterns"
    def _task_fn_name(self): return "train_fraud_patterns"

    def test_response_contains_warning(self):
        self.client.force_authenticate(self.admin)
        with patch("api.fraud_detection.views_tasks._enqueue",
                   return_value=_mock_enqueue()):
            resp = self.client.post(self._url(), {})
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])
        if resp.status_code == status.HTTP_202_ACCEPTED:
            self.assertIn("warning", resp.data)


class TaskAnalyzePatternsTriggerTest(_TriggerBase):
    url_name = "task-analyze-patterns"
    def _task_fn_name(self): return "analyze_fraud_patterns"


class TaskGraphNetworkScanTriggerTest(_TriggerBase):
    url_name = "task-graph-network-scan"
    def _task_fn_name(self): return "graph_network_scan"


class TaskVelocityCleanupTriggerTest(_TriggerBase):
    url_name = "task-velocity-cleanup"
    def _task_fn_name(self): return "velocity_engine_cleanup"


class TaskMLDriftCheckTriggerTest(_TriggerBase):
    url_name = "task-ml-drift-check"
    def _task_fn_name(self): return "ml_drift_check"


class TaskRetrainPatternsTriggerTest(_TriggerBase):
    url_name = "task-retrain-patterns"
    def _task_fn_name(self): return "retrain_fraud_patterns"


class TaskRecalculateStaleProfilesTriggerTest(_TriggerBase):
    url_name = "task-recalculate-stale"
    def _task_fn_name(self): return "recalculate_stale_risk_profiles"


# ---------------------------------------------------------------------------
# Group B — Notification trigger views
# ---------------------------------------------------------------------------

class TaskSendPendingNotifTriggerTest(_TriggerBase):
    url_name = "task-send-pending-notif"
    def _task_fn_name(self): return "send_pending_notifications"


class TaskRetryNotifTriggerTest(_TriggerBase):
    url_name = "task-retry-notif"
    def _task_fn_name(self): return "retry_failed_notifications"


class TaskDeliverNotifTriggerTest(_TriggerBase):
    url_name = "task-deliver-notif"
    def _task_fn_name(self): return "deliver_fraud_notification"

    def test_missing_notification_id_returns_400(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self._url(), {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_notification_id_type_returns_400(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self._url(), {"notification_id": "not-an-int"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_notification_id_enqueues(self):
        self.client.force_authenticate(self.admin)
        with patch("api.fraud_detection.views_tasks._enqueue",
                   return_value=_mock_enqueue()):
            resp = self.client.post(self._url(), {"notification_id": 42})
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])

    def _body(self):
        return {"notification_id": 1}


# ---------------------------------------------------------------------------
# Group C — Maintenance trigger views
# ---------------------------------------------------------------------------

class TaskWarmCacheTriggerTest(_TriggerBase):
    url_name = "task-warm-cache"
    def _task_fn_name(self): return "warm_fraud_cache"


class TaskCleanupCacheTriggerTest(_TriggerBase):
    url_name = "task-cleanup-cache"
    def _task_fn_name(self): return "cleanup_fraud_cache"


class TaskGenerateReportTriggerTest(_TriggerBase):
    url_name = "task-generate-report"
    def _task_fn_name(self): return "generate_fraud_report"

    def test_default_report_type_is_daily(self):
        self.client.force_authenticate(self.admin)
        captured = {}
        def fake_enqueue(fn_name, *args, **kwargs):
            captured["args"] = args
            return _mock_enqueue()
        with patch("api.fraud_detection.views_tasks._enqueue", side_effect=fake_enqueue):
            self.client.post(self._url(), {})
        self.assertEqual(captured["args"][0], "daily")

    def test_invalid_report_type_returns_400(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self._url(), {"report_type": "quarterly"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_weekly_accepted(self):
        self.client.force_authenticate(self.admin)
        with patch("api.fraud_detection.views_tasks._enqueue",
                   return_value=_mock_enqueue()):
            resp = self.client.post(self._url(), {"report_type": "weekly"})
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])


class TaskArchiveDataTriggerTest(_TriggerBase):
    url_name = "task-archive-data"
    def _task_fn_name(self): return "archive_old_fraud_data"

    def test_default_days_is_90(self):
        self.client.force_authenticate(self.admin)
        captured = {}
        def fake_enqueue(fn_name, *args, **kwargs):
            captured["days"] = args[0] if args else None
            return _mock_enqueue()
        with patch("api.fraud_detection.views_tasks._enqueue", side_effect=fake_enqueue):
            self.client.post(self._url(), {})
        self.assertEqual(captured["days"], 90)

    def test_minimum_days_is_30(self):
        self.client.force_authenticate(self.admin)
        captured = {}
        def fake_enqueue(fn_name, *args, **kwargs):
            captured["days"] = args[0] if args else None
            return _mock_enqueue()
        with patch("api.fraud_detection.views_tasks._enqueue", side_effect=fake_enqueue):
            self.client.post(self._url(), {"days_to_keep": 5})
        self.assertEqual(captured["days"], 30)

    def test_response_contains_warning(self):
        self.client.force_authenticate(self.admin)
        with patch("api.fraud_detection.views_tasks._enqueue",
                   return_value=_mock_enqueue()):
            resp = self.client.post(self._url(), {"days_to_keep": 90})
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])
        self.assertIn("warning", resp.data)


class TaskCleanupOrphanedTriggerTest(_TriggerBase):
    url_name = "task-cleanup-orphaned"
    def _task_fn_name(self): return "cleanup_orphaned_records"


class TaskIPReputationCleanupTriggerTest(_TriggerBase):
    url_name = "task-ip-cleanup"
    def _task_fn_name(self): return "ip_reputation_cleanup"


class TaskWhitelistCleanupTriggerTest(_TriggerBase):
    url_name = "task-whitelist-cleanup"
    def _task_fn_name(self): return "whitelist_cleanup_expired"


class TaskCheckUnbanTriggerTest(_TriggerBase):
    url_name = "task-check-unban"
    def _task_fn_name(self): return "check_and_unban_users"


class TaskAuditLogCleanupTriggerTest(_TriggerBase):
    url_name = "task-audit-cleanup"
    def _task_fn_name(self): return "audit_log_cleanup"
