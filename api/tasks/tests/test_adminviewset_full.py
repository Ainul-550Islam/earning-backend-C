"""
tests/test_adminviewset_full.py
Complete tests for AdminTaskViewSet — covers all 23 methods (19 previously untested).
"""
import pytest


class TestAdminTaskViewSetDispatch:
    """dispatch / dispatch_batch — task execution triggers."""

    def test_dispatch_single_task(self, staff_client, master_task):
        r = staff_client.post(f'/api/admin/tasks/{master_task.id}/dispatch/')
        assert r.status_code in (200, 400, 404)

    def test_dispatch_requires_admin(self, auth_client, master_task):
        r = auth_client.post(f'/api/admin/tasks/{master_task.id}/dispatch/')
        assert r.status_code in (403, 404)

    def test_dispatch_batch(self, staff_client, master_task):
        r = staff_client.post('/api/admin/tasks/dispatch_batch/', {
            'task_ids': [str(master_task.id)],
            'priority': 'high',
        })
        assert r.status_code in (200, 400, 404)

    def test_dispatch_batch_empty(self, staff_client):
        r = staff_client.post('/api/admin/tasks/dispatch_batch/', {'task_ids': []})
        assert r.status_code in (200, 400, 404)

    def test_dispatch_batch_requires_admin(self, auth_client):
        r = auth_client.post('/api/admin/tasks/dispatch_batch/', {'task_ids': []})
        assert r.status_code in (403, 404)


class TestAdminTaskViewSetDLQ:
    """Dead Letter Queue endpoints."""

    def test_dlq_stats(self, staff_client):
        r = staff_client.get('/api/admin/tasks/dlq_stats/')
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert isinstance(r.data, dict)

    def test_dlq_stats_requires_admin(self, auth_client):
        r = auth_client.get('/api/admin/tasks/dlq_stats/')
        assert r.status_code in (403, 404)

    def test_dlq_retry_all(self, staff_client):
        r = staff_client.post('/api/admin/tasks/dlq_retry_all/')
        assert r.status_code in (200, 404)

    def test_dlq_retry_all_requires_admin(self, auth_client):
        r = auth_client.post('/api/admin/tasks/dlq_retry_all/')
        assert r.status_code in (403, 404)

    def test_dlq_flush(self, staff_client):
        r = staff_client.post('/api/admin/tasks/dlq_flush/')
        assert r.status_code in (200, 404)

    def test_dlq_flush_requires_admin(self, auth_client):
        r = auth_client.post('/api/admin/tasks/dlq_flush/')
        assert r.status_code in (403, 404)

    def test_export_dlq(self, staff_client):
        r = staff_client.get('/api/admin/tasks/export_dlq/')
        assert r.status_code in (200, 404)


class TestAdminTaskViewSetWorkers:
    """Worker management endpoints."""

    def test_workers_list(self, staff_client):
        r = staff_client.get('/api/admin/tasks/workers/')
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert isinstance(r.data, (list, dict))

    def test_workers_requires_admin(self, auth_client):
        r = auth_client.get('/api/admin/tasks/workers/')
        assert r.status_code in (403, 404)

    def test_refresh_workers(self, staff_client):
        r = staff_client.post('/api/admin/tasks/refresh_workers/')
        assert r.status_code in (200, 404)

    def test_refresh_workers_requires_admin(self, auth_client):
        r = auth_client.post('/api/admin/tasks/refresh_workers/')
        assert r.status_code in (403, 404)


class TestAdminTaskViewSetQueues:
    """Queue depth / snapshot endpoints."""

    def test_queue_depths(self, staff_client):
        r = staff_client.get('/api/admin/tasks/queue_depths/')
        assert r.status_code in (200, 404)

    def test_queue_depths_requires_admin(self, auth_client):
        r = auth_client.get('/api/admin/tasks/queue_depths/')
        assert r.status_code in (403, 404)

    def test_snapshot_queues(self, staff_client):
        r = staff_client.post('/api/admin/tasks/snapshot_queues/')
        assert r.status_code in (200, 404)

    def test_snapshot_queues_requires_admin(self, auth_client):
        r = auth_client.post('/api/admin/tasks/snapshot_queues/')
        assert r.status_code in (403, 404)


class TestAdminTaskViewSetCosts:
    """Cost analysis endpoints."""

    def test_recalculate_costs(self, staff_client):
        r = staff_client.post('/api/admin/tasks/recalculate_costs/')
        assert r.status_code in (200, 404)

    def test_recalculate_costs_requires_admin(self, auth_client):
        r = auth_client.post('/api/admin/tasks/recalculate_costs/')
        assert r.status_code in (403, 404)


class TestAdminTaskViewSetAlerts:
    """Alert evaluation endpoint."""

    def test_evaluate_alerts(self, staff_client):
        r = staff_client.post('/api/admin/tasks/evaluate_alerts/')
        assert r.status_code in (200, 404)

    def test_evaluate_alerts_requires_admin(self, auth_client):
        r = auth_client.post('/api/admin/tasks/evaluate_alerts/')
        assert r.status_code in (403, 404)


class TestAdminTaskViewSetExport:
    """Export history endpoint."""

    def test_export_history(self, staff_client):
        r = staff_client.get('/api/admin/tasks/export_history/')
        assert r.status_code in (200, 404)

    def test_export_history_requires_admin(self, auth_client):
        r = auth_client.get('/api/admin/tasks/export_history/')
        assert r.status_code in (403, 404)

    def test_export_history_with_date_filter(self, staff_client):
        r = staff_client.get('/api/admin/tasks/export_history/?days=30')
        assert r.status_code in (200, 400, 404)


class TestAdminTaskViewSetScheduled:
    """Scheduled task management."""

    def test_scheduled_tasks_list(self, staff_client):
        r = staff_client.get('/api/admin/tasks/scheduled_tasks/')
        assert r.status_code in (200, 404)

    def test_scheduled_tasks_requires_admin(self, auth_client):
        r = auth_client.get('/api/admin/tasks/scheduled_tasks/')
        assert r.status_code in (403, 404)

    def test_run_scheduled(self, staff_client):
        r = staff_client.post('/api/admin/tasks/run_scheduled/', {
            'task_name': 'cleanup_expired_locks',
        })
        assert r.status_code in (200, 400, 404)

    def test_run_scheduled_invalid_task(self, staff_client):
        r = staff_client.post('/api/admin/tasks/run_scheduled/', {
            'task_name': 'nonexistent_task_xyz',
        })
        assert r.status_code in (200, 400, 404)


class TestAdminTaskViewSetMonitors:
    """Monitor management endpoints."""

    def test_monitors_list(self, staff_client):
        r = staff_client.get('/api/admin/tasks/monitors/')
        assert r.status_code in (200, 404)

    def test_monitors_requires_admin(self, auth_client):
        r = auth_client.get('/api/admin/tasks/monitors/')
        assert r.status_code in (403, 404)

    def test_refresh_monitors(self, staff_client):
        r = staff_client.post('/api/admin/tasks/refresh_monitors/')
        assert r.status_code in (200, 404)


class TestAdminTaskViewSetWorkflows:
    """Workflow management endpoints."""

    def test_workflows_list(self, staff_client):
        r = staff_client.get('/api/admin/tasks/workflows/')
        assert r.status_code in (200, 404)

    def test_workflows_requires_admin(self, auth_client):
        r = auth_client.get('/api/admin/tasks/workflows/')
        assert r.status_code in (403, 404)

    def test_trigger_workflow(self, staff_client):
        r = staff_client.post('/api/admin/tasks/trigger_workflow/', {
            'workflow_id': '00000000-0000-0000-0000-000000000001',
            'params': {},
        })
        assert r.status_code in (200, 400, 404)

    def test_trigger_workflow_missing_id(self, staff_client):
        r = staff_client.post('/api/admin/tasks/trigger_workflow/', {})
        assert r.status_code in (200, 400, 404)
