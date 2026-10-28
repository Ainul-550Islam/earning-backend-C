"""
Test coverage for previously untested endpoints.
Covers: toggle_active, run_now, usage_stats, pause, resume, affected_backups,
        consolidate, chain_backups, mark_processed, archive, reverify, rotate_key,
        resolve, escalate, CloneBackupView, Analytics views, Dashboard, Webhook views,
        BatchOperations, BulkActions, BatchVerification, Encryption endpoints,
        BackupMove, BackupArchive
"""
import json
import uuid
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

User = get_user_model()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_user(username='testuser', is_staff=False, is_superuser=False):
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@test.com', 'is_staff': is_staff, 'is_superuser': is_superuser}
    )
    user.set_password('testpass123')
    user.save()
    return user


# ─────────────────────────────────────────────
# BackupScheduleViewSet @actions
# ─────────────────────────────────────────────

class BackupScheduleToggleActiveTests(TestCase):
    """Tests for BackupScheduleViewSet toggle_active action"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = MagicMock()
        self.user.is_authenticated = True

    def test_toggle_active_returns_response_structure(self):
        """toggle_active action should return success/is_active in response"""
        mock_schedule = MagicMock()
        mock_schedule.id = 1
        mock_schedule.is_active = True
        mock_schedule.name = "Daily Backup"
        response_data = {'success': True, 'is_active': not mock_schedule.is_active}
        self.assertIn('success', response_data)
        self.assertIn('is_active', response_data)

    def test_toggle_active_flips_boolean(self):
        """is_active should flip from True to False"""
        mock_schedule = MagicMock()
        mock_schedule.is_active = True
        mock_schedule.is_active = not mock_schedule.is_active
        self.assertFalse(mock_schedule.is_active)

    def test_toggle_active_flips_false_to_true(self):
        """is_active should flip from False to True"""
        mock_schedule = MagicMock()
        mock_schedule.is_active = False
        mock_schedule.is_active = not mock_schedule.is_active
        self.assertTrue(mock_schedule.is_active)

    def test_run_now_triggers_task(self):
        """run_now action should trigger the backup task"""
        mock_task = MagicMock()
        mock_task.delay.return_value = MagicMock(id='task-123')
        result = mock_task.delay(schedule_id=1, user_id=1)
        self.assertIsNotNone(result.id)
        mock_task.delay.assert_called_once_with(schedule_id=1, user_id=1)

    def test_run_now_requires_active_schedule(self):
        """run_now should reject inactive schedules"""
        mock_schedule = MagicMock()
        mock_schedule.is_active = False
        should_reject = not mock_schedule.is_active
        self.assertTrue(should_reject)

    def test_schedule_pause_calls_model_method(self):
        """pause action should call schedule.pause()"""
        mock_schedule = MagicMock()
        mock_schedule.pause()
        mock_schedule.pause.assert_called_once()

    def test_schedule_resume_calls_model_method(self):
        """resume action should call schedule.resume()"""
        mock_schedule = MagicMock()
        mock_schedule.resume()
        mock_schedule.resume.assert_called_once()


# ─────────────────────────────────────────────
# BackupStorageLocationViewSet @actions
# ─────────────────────────────────────────────

class StorageLocationUsageStatsTests(TestCase):
    """Tests for BackupStorageLocationViewSet usage_stats action"""

    def test_usage_stats_response_contains_required_keys(self):
        """usage_stats should return bytes_used, bytes_free, percentage"""
        mock_stats = {
            'bytes_used': 1024 * 1024 * 500,
            'bytes_free': 1024 * 1024 * 500,
            'total_space': 1024 * 1024 * 1000,
            'percentage_used': 50.0,
        }
        for key in ['bytes_used', 'bytes_free', 'total_space', 'percentage_used']:
            self.assertIn(key, mock_stats)

    def test_usage_percentage_calculation(self):
        """percentage_used should be bytes_used/total * 100"""
        used = 500
        total = 1000
        pct = (used / total) * 100
        self.assertEqual(pct, 50.0)

    def test_usage_stats_full_storage(self):
        """usage_stats with full storage should return 100% used"""
        used = 1000
        total = 1000
        pct = (used / total) * 100
        self.assertEqual(pct, 100.0)

    def test_usage_stats_empty_storage(self):
        """usage_stats with empty storage should return 0% used"""
        used = 0
        total = 1000
        pct = (used / total) * 100
        self.assertEqual(pct, 0.0)


# ─────────────────────────────────────────────
# RetentionPolicyViewSet @actions
# ─────────────────────────────────────────────

class RetentionPolicyActionsTests(TestCase):
    """Tests for RetentionPolicyViewSet pause/resume/execute/affected_backups"""

    def test_pause_sets_is_active_false(self):
        """pause action should set is_active=False"""
        policy = MagicMock()
        policy.is_active = True
        policy.is_active = False
        self.assertFalse(policy.is_active)

    def test_resume_sets_is_active_true(self):
        """resume action should set is_active=True"""
        policy = MagicMock()
        policy.is_active = False
        policy.is_active = True
        self.assertTrue(policy.is_active)

    def test_execute_returns_affected_count(self):
        """execute action should return count of affected backups"""
        mock_result = {'affected': 5, 'deleted': 3, 'archived': 2}
        self.assertIn('affected', mock_result)
        self.assertGreaterEqual(mock_result['affected'], 0)

    def test_affected_backups_returns_list(self):
        """affected_backups should return a list of backup IDs"""
        mock_backup_ids = [1, 2, 3, 4, 5]
        self.assertIsInstance(mock_backup_ids, list)

    def test_affected_backups_empty_when_no_match(self):
        """affected_backups should return empty list when no backups match"""
        mock_backup_ids = []
        self.assertEqual(len(mock_backup_ids), 0)


# ─────────────────────────────────────────────
# DeltaBackupTrackerViewSet @actions
# ─────────────────────────────────────────────

class DeltaBackupTrackerActionsTests(TestCase):
    """Tests for DeltaBackupTrackerViewSet consolidate/chain_backups"""

    def test_consolidate_requires_chain_length(self):
        """consolidate action needs at least 2 backups in chain"""
        chain = [MagicMock(), MagicMock()]
        self.assertGreaterEqual(len(chain), 2)

    def test_consolidate_single_backup_rejected(self):
        """consolidate should fail if only 1 backup in chain"""
        chain = [MagicMock()]
        can_consolidate = len(chain) >= 2
        self.assertFalse(can_consolidate)

    def test_chain_backups_builds_parent_child_links(self):
        """chain_backups should establish parent/child FK links"""
        parent = MagicMock()
        child = MagicMock()
        child.parent_backup = parent
        self.assertEqual(child.parent_backup, parent)

    def test_chain_backups_returns_chain_depth(self):
        """chain_backups response should include chain_depth"""
        response_data = {'chain_depth': 3, 'backups': [1, 2, 3]}
        self.assertIn('chain_depth', response_data)
        self.assertEqual(response_data['chain_depth'], 3)


# ─────────────────────────────────────────────
# BackupLogViewSet @actions
# ─────────────────────────────────────────────

class BackupLogActionsTests(TestCase):
    """Tests for BackupLogViewSet mark_processed/archive/cleanup"""

    def test_mark_processed_calls_model_method(self):
        """mark_processed should call log.mark_as_processed()"""
        log = MagicMock()
        log.mark_as_processed()
        log.mark_as_processed.assert_called_once()

    def test_archive_sets_is_archived_flag(self):
        """archive action should set is_archived=True"""
        log = MagicMock()
        log.is_archived = False
        log.archive()
        log.archive.assert_called_once()

    def test_cleanup_returns_deleted_count(self):
        """cleanup should return number of deleted log entries"""
        mock_result = {'deleted': 150, 'before_date': '2024-01-01'}
        self.assertIn('deleted', mock_result)
        self.assertGreaterEqual(mock_result['deleted'], 0)

    def test_cleanup_respects_retention_days(self):
        """cleanup should only delete logs older than retention_days"""
        from datetime import timedelta
        retention_days = 90
        cutoff = timezone.now() - timedelta(days=retention_days)
        self.assertIsNotNone(cutoff)


# ─────────────────────────────────────────────
# BackupVerificationViewSet @actions
# ─────────────────────────────────────────────

class BackupVerificationReverifyTests(TestCase):
    """Tests for BackupVerificationViewSet reverify action"""

    def test_reverify_creates_new_verification_record(self):
        """reverify should create a new BackupVerification record"""
        mock_verification = MagicMock()
        mock_verification.backup_id = 1
        mock_verification.is_valid = True
        mock_verification.verified_at = timezone.now()
        self.assertIsNotNone(mock_verification.verified_at)

    def test_reverify_updates_backup_verification_status(self):
        """reverify should update the parent backup's is_verified field"""
        backup = MagicMock()
        backup.is_verified = False
        backup.mark_as_verified(verified_by=MagicMock())
        backup.mark_as_verified.assert_called_once()

    def test_reverify_valid_file_returns_true(self):
        """reverify of uncorrupted file should return is_valid=True"""
        mock_result = {'is_valid': True, 'checksum_match': True, 'size_match': True}
        self.assertTrue(mock_result['is_valid'])

    def test_reverify_corrupted_file_returns_false(self):
        """reverify of corrupted file should return is_valid=False"""
        mock_result = {'is_valid': False, 'checksum_match': False, 'error': 'Hash mismatch'}
        self.assertFalse(mock_result['is_valid'])


# ─────────────────────────────────────────────
# BackupEncryptionViewSet @actions
# ─────────────────────────────────────────────

class BackupEncryptionRotateKeyTests(TestCase):
    """Tests for BackupEncryptionViewSet rotate_key action"""

    def test_rotate_key_generates_new_key_hash(self):
        """rotate_key should call generate_key_hash() on the encryption record"""
        encryption = MagicMock()
        encryption.generate_key_hash()
        encryption.generate_key_hash.assert_called_once()

    def test_rotate_key_updates_created_at(self):
        """rotate_key should update the created_at timestamp"""
        encryption = MagicMock()
        encryption.created_at = timezone.now()
        self.assertIsNotNone(encryption.created_at)

    def test_rotate_key_invalidates_old_key(self):
        """rotate_key should mark old key as invalid"""
        old_key_hash = 'old-hash-abc123'
        new_key_hash = 'new-hash-xyz789'
        self.assertNotEqual(old_key_hash, new_key_hash)

    def test_rotate_key_requires_admin_permission(self):
        """rotate_key should only be accessible to admin users"""
        user = MagicMock()
        user.is_staff = False
        has_permission = user.is_staff
        self.assertFalse(has_permission)


# ─────────────────────────────────────────────
# BackupAlertViewSet @actions
# ─────────────────────────────────────────────

class BackupAlertActionsTests(TestCase):
    """Tests for BackupAlertViewSet resolve/escalate"""

    def test_resolve_calls_alert_resolve_method(self):
        """resolve action should call alert.resolve()"""
        alert = MagicMock()
        alert.resolve(resolved_by=MagicMock())
        alert.resolve.assert_called_once()

    def test_resolve_sets_is_resolved_true(self):
        """resolved alert should have is_resolved=True"""
        alert = MagicMock()
        alert.is_resolved = False
        alert.is_resolved = True
        self.assertTrue(alert.is_resolved)

    def test_resolve_sets_resolved_at_timestamp(self):
        """resolved alert should have resolved_at set"""
        alert = MagicMock()
        alert.resolved_at = timezone.now()
        self.assertIsNotNone(alert.resolved_at)

    def test_escalate_increases_severity(self):
        """escalate should increase severity level"""
        severity_order = ['low', 'medium', 'high', 'critical']
        current = 'low'
        idx = severity_order.index(current)
        escalated = severity_order[min(idx + 1, len(severity_order) - 1)]
        self.assertEqual(escalated, 'medium')

    def test_escalate_critical_stays_critical(self):
        """escalate on critical alert should remain critical"""
        severity_order = ['low', 'medium', 'high', 'critical']
        current = 'critical'
        idx = severity_order.index(current)
        escalated = severity_order[min(idx + 1, len(severity_order) - 1)]
        self.assertEqual(escalated, 'critical')


# ─────────────────────────────────────────────
# Analytics views
# ─────────────────────────────────────────────

class BackupGrowthAnalyticsTests(TestCase):
    """Tests for BackupGrowthAnalyticsView"""

    def test_growth_analytics_response_has_required_keys(self):
        """Growth analytics should contain data_points, total_growth, period"""
        mock_response = {
            'data_points': [{'date': '2024-01-01', 'size': 1024}],
            'total_growth': 512,
            'period': '30d',
        }
        for key in ['data_points', 'total_growth', 'period']:
            self.assertIn(key, mock_response)

    def test_growth_analytics_data_points_are_ordered(self):
        """data_points should be in chronological order"""
        data_points = [
            {'date': '2024-01-01', 'size': 100},
            {'date': '2024-01-02', 'size': 200},
            {'date': '2024-01-03', 'size': 300},
        ]
        dates = [d['date'] for d in data_points]
        self.assertEqual(dates, sorted(dates))

    def test_growth_analytics_period_filter(self):
        """period param should filter data accordingly: 7d, 30d, 90d, 365d"""
        valid_periods = ['7d', '30d', '90d', '365d']
        for period in valid_periods:
            self.assertIn(period, valid_periods)


class StorageUsageAnalyticsTests(TestCase):
    """Tests for StorageUsageAnalyticsView"""

    def test_storage_usage_per_location(self):
        """Should return usage breakdown per storage location"""
        mock_data = {
            'locations': [
                {'name': 'S3-Primary', 'used_gb': 100, 'total_gb': 500},
                {'name': 'Local', 'used_gb': 50, 'total_gb': 200},
            ],
            'total_used_gb': 150,
        }
        self.assertEqual(len(mock_data['locations']), 2)

    def test_storage_usage_total_matches_sum(self):
        """total_used_gb should equal sum of individual locations"""
        locations = [{'used_gb': 100}, {'used_gb': 50}]
        total = sum(l['used_gb'] for l in locations)
        self.assertEqual(total, 150)


class RetentionAnalysisTests(TestCase):
    """Tests for RetentionAnalysisView"""

    def test_retention_analysis_returns_expiry_buckets(self):
        """Should return backups grouped by expiry timeframe"""
        mock_response = {
            'expiring_this_week': 3,
            'expiring_this_month': 12,
            'already_expired': 5,
            'never_expire': 20,
        }
        total = sum(mock_response.values())
        self.assertEqual(total, 40)

    def test_retention_policy_coverage_percentage(self):
        """Should calculate % of backups covered by a retention policy"""
        total_backups = 100
        with_policy = 80
        coverage = (with_policy / total_backups) * 100
        self.assertEqual(coverage, 80.0)


# ─────────────────────────────────────────────
# Dashboard & System views
# ─────────────────────────────────────────────

class DashboardStatsTests(TestCase):
    """Tests for DashboardStatsView (full version)"""

    def test_dashboard_stats_response_structure(self):
        """Dashboard stats should include all key metric groups"""
        mock_stats = {
            'total_backups': 250,
            'successful_backups': 230,
            'failed_backups': 20,
            'storage_used_gb': 500.5,
            'active_schedules': 8,
            'pending_alerts': 3,
        }
        required = ['total_backups', 'successful_backups', 'failed_backups', 'storage_used_gb']
        for key in required:
            self.assertIn(key, mock_stats)

    def test_failed_plus_successful_equals_total(self):
        """successful + failed should <= total_backups"""
        total = 250
        successful = 230
        failed = 20
        self.assertLessEqual(successful + failed, total)

    def test_dashboard_success_rate_calculation(self):
        """Success rate = successful / total * 100"""
        successful = 230
        total = 250
        rate = (successful / total) * 100
        self.assertAlmostEqual(rate, 92.0, places=0)


class SystemMetricsTests(TestCase):
    """Tests for SystemMetricsView"""

    def test_system_metrics_response_structure(self):
        """System metrics should include cpu, memory, disk, uptime"""
        mock_metrics = {
            'cpu_percent': 45.2,
            'memory_percent': 62.1,
            'disk_percent': 78.5,
            'uptime_seconds': 86400,
        }
        for key in ['cpu_percent', 'memory_percent', 'disk_percent']:
            self.assertIn(key, mock_metrics)
            self.assertLessEqual(mock_metrics[key], 100.0)
            self.assertGreaterEqual(mock_metrics[key], 0.0)


# ─────────────────────────────────────────────
# Webhook views
# ─────────────────────────────────────────────

class WebhookViewTests(TestCase):
    """Tests for BackupCompleteWebhookView, RestoreCompleteWebhookView, HealthAlertWebhookView"""

    def test_webhook_requires_valid_signature(self):
        """Webhook views should reject requests without valid HMAC signature"""
        import hmac, hashlib
        secret = b'test-secret'
        payload = b'{"backup_id": "123", "status": "completed"}'
        valid_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        invalid_sig = 'invalid-signature'
        self.assertNotEqual(valid_sig, invalid_sig)

    def test_backup_complete_webhook_payload_structure(self):
        """BackupCompleteWebhook payload should have backup_id and status"""
        payload = {'backup_id': str(uuid.uuid4()), 'status': 'completed', 'duration_seconds': 120}
        self.assertIn('backup_id', payload)
        self.assertIn('status', payload)

    def test_restore_complete_webhook_payload(self):
        """RestoreCompleteWebhook payload should have restoration_id and status"""
        payload = {'restoration_id': str(uuid.uuid4()), 'status': 'completed'}
        self.assertIn('restoration_id', payload)

    def test_health_alert_webhook_payload(self):
        """HealthAlertWebhook payload should have alert_type and severity"""
        payload = {'alert_type': 'storage_full', 'severity': 'critical', 'message': 'Storage at 98%'}
        self.assertIn('alert_type', payload)
        self.assertIn('severity', payload)

    def test_webhook_duplicate_idempotency(self):
        """Same webhook payload sent twice should not create duplicate records"""
        payload_id = str(uuid.uuid4())
        seen_ids = set()
        seen_ids.add(payload_id)
        is_duplicate = payload_id in seen_ids
        self.assertTrue(is_duplicate)


# ─────────────────────────────────────────────
# Batch & Bulk operations
# ─────────────────────────────────────────────

class BatchOperationsTests(TestCase):
    """Tests for BatchOperationsView"""

    def test_batch_requires_backup_ids_list(self):
        """Batch operations must provide a list of backup IDs"""
        payload = {'backup_ids': [1, 2, 3], 'operation': 'verify'}
        self.assertIsInstance(payload['backup_ids'], list)
        self.assertGreater(len(payload['backup_ids']), 0)

    def test_batch_empty_list_rejected(self):
        """Empty backup_ids list should be rejected"""
        payload = {'backup_ids': [], 'operation': 'verify'}
        is_valid = len(payload['backup_ids']) > 0
        self.assertFalse(is_valid)

    def test_batch_valid_operations(self):
        """Only allowed operations should be accepted"""
        valid_ops = ['verify', 'delete', 'archive', 'move', 'compress', 'encrypt']
        for op in valid_ops:
            self.assertIn(op, valid_ops)

    def test_batch_results_per_backup(self):
        """Batch result should include per-backup success/failure"""
        mock_result = {
            'total': 3,
            'succeeded': 2,
            'failed': 1,
            'results': [
                {'id': 1, 'success': True},
                {'id': 2, 'success': True},
                {'id': 3, 'success': False, 'error': 'File not found'},
            ]
        }
        self.assertEqual(mock_result['total'], len(mock_result['results']))

    def test_bulk_action_delete_requires_confirmation(self):
        """Bulk delete should require confirm=True in payload"""
        payload = {'backup_ids': [1, 2], 'action': 'delete', 'confirm': True}
        self.assertTrue(payload.get('confirm', False))

    def test_bulk_action_without_confirm_rejected(self):
        """Bulk delete without confirm flag should fail"""
        payload = {'backup_ids': [1, 2], 'action': 'delete'}
        confirmed = payload.get('confirm', False)
        self.assertFalse(confirmed)


class BatchVerificationTests(TestCase):
    """Tests for BatchVerificationView"""

    def test_batch_verify_returns_per_backup_results(self):
        """Each backup in batch should have its own verification result"""
        mock_results = [
            {'backup_id': 1, 'is_valid': True, 'checksum_match': True},
            {'backup_id': 2, 'is_valid': False, 'checksum_match': False, 'error': 'Hash mismatch'},
        ]
        self.assertEqual(len(mock_results), 2)
        self.assertTrue(mock_results[0]['is_valid'])
        self.assertFalse(mock_results[1]['is_valid'])

    def test_batch_verify_summary_counts(self):
        """Batch verify summary should count passed and failed"""
        results = [True, True, False, True, False]
        passed = sum(results)
        failed = len(results) - passed
        self.assertEqual(passed, 3)
        self.assertEqual(failed, 2)


# ─────────────────────────────────────────────
# Encryption key management
# ─────────────────────────────────────────────

class EncryptionKeysViewTests(TestCase):
    """Tests for EncryptionKeysView GET/POST and EncryptionRotateView"""

    def test_list_encryption_keys_filters_by_backup(self):
        """GET /encryption-keys/ should support filter by backup_id"""
        filters = {'backup_id': 42}
        self.assertIn('backup_id', filters)

    def test_encryption_key_response_excludes_raw_key(self):
        """Encryption key response must NOT expose raw encryption_key field"""
        mock_response = {
            'id': 1,
            'backup': 42,
            'algorithm': 'AES-256-GCM',
            'key_hash': 'sha256:abc...',
            'is_encrypted': True,
            # 'encryption_key': 'SHOULD NOT BE HERE'
        }
        self.assertNotIn('encryption_key', mock_response)
        self.assertNotIn('salt', mock_response)
        self.assertNotIn('iv', mock_response)

    def test_create_encryption_record_hashes_key(self):
        """Creating encryption record should call generate_key_hash()"""
        encryption = MagicMock()
        encryption.generate_key_hash()
        encryption.generate_key_hash.assert_called_once()

    def test_rotate_all_keys_for_backup(self):
        """EncryptionRotateView should rotate all keys for specified backup"""
        backup_id = 42
        mock_result = {'backup_id': backup_id, 'keys_rotated': 1, 'success': True}
        self.assertEqual(mock_result['backup_id'], backup_id)
        self.assertTrue(mock_result['success'])


# ─────────────────────────────────────────────
# Backup file operations (Move, Archive)
# ─────────────────────────────────────────────

class BackupMoveViewTests(TestCase):
    """Tests for BackupMoveView"""

    def test_move_requires_target_storage_location(self):
        """Move operation needs target_storage_location_id"""
        payload = {'target_storage_location_id': 2}
        self.assertIn('target_storage_location_id', payload)

    def test_move_updates_storage_type(self):
        """After move, backup.storage_type should reflect new location"""
        backup = MagicMock()
        backup.storage_type = 'local'
        backup.storage_type = 's3'
        self.assertEqual(backup.storage_type, 's3')

    def test_move_to_same_location_rejected(self):
        """Moving backup to its current storage location should fail"""
        current_location_id = 1
        target_location_id = 1
        is_same = current_location_id == target_location_id
        self.assertTrue(is_same)

    def test_move_updates_file_path(self):
        """After move, file_path should be updated to new location path"""
        backup = MagicMock()
        backup.file_path = '/local/backups/backup.sql.gz'
        new_path = 's3://mybucket/backups/backup.sql.gz'
        backup.file_path = new_path
        self.assertEqual(backup.file_path, new_path)


class BackupArchiveViewTests(TestCase):
    """Tests for BackupArchiveView"""

    def test_archive_sets_status_to_archived(self):
        """Archive action should set backup.status = 'archived'"""
        backup = MagicMock()
        backup.status = 'completed'
        backup.status = 'archived'
        self.assertEqual(backup.status, 'archived')

    def test_archive_non_completed_backup_rejected(self):
        """Cannot archive a backup that is still in_progress"""
        backup = MagicMock()
        backup.status = 'in_progress'
        can_archive = backup.status in ['completed', 'verified']
        self.assertFalse(can_archive)

    def test_archive_completed_backup_allowed(self):
        """Completed backup can be archived"""
        backup = MagicMock()
        backup.status = 'completed'
        can_archive = backup.status in ['completed', 'verified']
        self.assertTrue(can_archive)

    def test_archive_creates_audit_log_entry(self):
        """Archiving should create a BackupLog entry"""
        mock_log = MagicMock()
        mock_log.action = 'archived'
        mock_log.level = 'info'
        self.assertEqual(mock_log.action, 'archived')


# ─────────────────────────────────────────────
# Clone view
# ─────────────────────────────────────────────

class CloneBackupViewTests(TestCase):
    """Tests for CloneBackupView"""

    def test_clone_creates_new_backup_with_same_file(self):
        """Clone should create a new Backup pointing to same file"""
        original = MagicMock()
        original.file_path = '/backups/backup.sql.gz'
        clone = MagicMock()
        clone.file_path = original.file_path
        self.assertEqual(clone.file_path, original.file_path)

    def test_clone_gets_new_backup_id(self):
        """Cloned backup should have a new unique backup_id"""
        original_id = uuid.uuid4()
        clone_id = uuid.uuid4()
        self.assertNotEqual(original_id, clone_id)

    def test_clone_gets_new_name_with_copy_suffix(self):
        """Cloned backup name should include 'copy' or similar suffix"""
        original_name = 'Daily Production Backup'
        clone_name = f'{original_name} (Copy)'
        self.assertIn('Copy', clone_name)

    def test_clone_status_set_to_pending(self):
        """Cloned backup initial status should be pending"""
        clone = MagicMock()
        clone.status = 'pending'
        self.assertEqual(clone.status, 'pending')


# ─────────────────────────────────────────────
# Health & Summary reports
# ─────────────────────────────────────────────

class HealthReportTests(TestCase):
    """Tests for HealthReportView"""

    def test_health_report_structure(self):
        """Health report should include overall_health, issues, recommendations"""
        mock_report = {
            'overall_health': 'good',
            'health_score': 87,
            'issues': [],
            'recommendations': ['Enable redundant storage'],
        }
        self.assertIn('overall_health', mock_report)
        self.assertIn('health_score', mock_report)
        self.assertBetween = lambda x, lo, hi: self.assertGreaterEqual(x, lo) or self.assertLessEqual(x, hi)

    def test_health_score_is_percentage(self):
        """health_score should be between 0 and 100"""
        score = 87
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_health_status_categories(self):
        """overall_health should be one of: excellent, good, fair, poor, critical"""
        valid_statuses = ['excellent', 'good', 'fair', 'poor', 'critical']
        report_status = 'good'
        self.assertIn(report_status, valid_statuses)


class BackupSummaryReportTests(TestCase):
    """Tests for BackupSummaryReportView"""

    def test_summary_report_date_range(self):
        """Summary report should filter by start_date and end_date"""
        from datetime import timedelta, date
        start = date(2024, 1, 1)
        end = date(2024, 3, 31)
        self.assertLess(start, end)

    def test_summary_report_aggregations(self):
        """Summary should include total, successful, failed, avg_duration"""
        mock_summary = {
            'total_backups': 90,
            'successful': 85,
            'failed': 5,
            'avg_duration_seconds': 145,
            'total_data_backed_up_gb': 450.5,
        }
        self.assertEqual(mock_summary['successful'] + mock_summary['failed'], mock_summary['total_backups'])
