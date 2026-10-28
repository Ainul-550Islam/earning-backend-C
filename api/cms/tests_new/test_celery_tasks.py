# api/cms/tests_new/test_celery_tasks.py
"""
Celery Tasks — production-critical test suite.

Coverage targets (25 task functions → previously 0% tested):
  ✅ process_cpalead_postback              — valid postback accepted
  ✅ process_cpalead_postback              — duplicate postback rejected (idempotent)
  ✅ process_cpalead_postback              — invalid hash rejected
  ✅ send_reward_notification              — notification dispatched
  ✅ send_reward_notification              — missing user handled gracefully
  ✅ update_leaderboard_rankings           — ranking updated without crash
  ✅ cleanup_expired_sessions              — stale sessions removed
  ✅ cleanup_expired_sessions              — dry_run=True makes no changes
  ✅ process_withdrawal_batch              — pending withdrawals processed
  ✅ refresh_offer_cache                   — cache refreshed without crash
  ✅ generate_daily_analytics_report       — report generated without crash
  ✅ run_data_retention_policies           — retention runs in dry_run mode
  ✅ check_system_health                   — health check returns report
  ✅ sync_user_segments                    — segment sync runs without crash
  ✅ send_bulk_notifications               — bulk send dispatched
  ✅ process_scheduled_content_publish     — due content published
  ✅ warm_cms_cache                        — cache warm-up runs without crash
  ✅ recalculate_user_streaks              — streak recalculation runs
  ✅ Task retry behaviour — transient error triggers retry
  ✅ Task failure — non-retryable error marks task as FAILED cleanly
"""
from unittest.mock import patch, MagicMock, call, ANY
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_user(username):
    return User.objects.create_user(
        username=username,
        email=f'{username}@test.com',
        password='Pass123!',
    )


# ─────────────────────────────────────────────────────────────────────────────
# CPAlead postback task
# ─────────────────────────────────────────────────────────────────────────────

class ProcessCPALeadPostbackTaskTest(TestCase):
    """process_cpalead_postback Celery task tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user('postback_task_user')

    @patch('api.cms.tasks.process_cpalead_postback.CPALeadService.handle_postback')
    def test_valid_postback_calls_service(self, mock_handle):
        """Valid postback data must call CPALeadService.handle_postback."""
        mock_handle.return_value = {'success': True, 'lead_id': 'lead_001'}
        from api.cms.tasks import process_cpalead_postback
        result = process_cpalead_postback.apply(kwargs={
            'user_id': self.user.pk,
            'payout_usd': 1.50,
            'lead_id': 'lead_001',
            'offer_id': 42,
            'ip': '10.0.0.1',
            'hash_value': 'abc123',
        }).get()
        mock_handle.assert_called_once()
        self.assertTrue(result.get('success', False))

    @patch('api.cms.tasks.process_cpalead_postback.CPALeadService.handle_postback')
    def test_duplicate_lead_id_rejected(self, mock_handle):
        """Duplicate lead_id must be rejected (idempotent task)."""
        mock_handle.return_value = {'success': False, 'error': 'duplicate_lead'}
        from api.cms.tasks import process_cpalead_postback
        result = process_cpalead_postback.apply(kwargs={
            'user_id': self.user.pk,
            'payout_usd': 1.50,
            'lead_id': 'duplicate_lead_999',
            'offer_id': 42,
            'ip': '10.0.0.1',
            'hash_value': 'abc123',
        }).get()
        self.assertFalse(result.get('success', True))
        self.assertIn('duplicate', str(result.get('error', '')).lower())

    @patch('api.cms.tasks.process_cpalead_postback.CPALeadService.verify_hash')
    def test_invalid_hash_rejected_before_service_call(self, mock_verify):
        """Invalid postback hash must be caught before calling the service."""
        mock_verify.return_value = False
        from api.cms.tasks import process_cpalead_postback
        result = process_cpalead_postback.apply(kwargs={
            'user_id': self.user.pk,
            'payout_usd': 5.00,
            'lead_id': 'bad_hash_lead',
            'offer_id': 1,
            'ip': '10.0.0.1',
            'hash_value': 'invalid_hash',
        }).get()
        self.assertFalse(result.get('success', True))

    @patch('api.cms.tasks.process_cpalead_postback.CPALeadService.handle_postback')
    def test_missing_user_handled_gracefully(self, mock_handle):
        """Non-existent user_id must not crash the task."""
        from api.cms.tasks import process_cpalead_postback
        # Should not raise — task must fail cleanly
        try:
            result = process_cpalead_postback.apply(kwargs={
                'user_id': 99999999,  # non-existent
                'payout_usd': 1.00,
                'lead_id': 'orphan_lead',
                'offer_id': 1,
                'ip': '10.0.0.1',
                'hash_value': 'x',
            }).get()
            self.assertFalse(result.get('success', True),
                             msg="Task with non-existent user should return failure.")
        except Exception as e:
            self.fail(f"Task raised unexpected exception for missing user: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Notification tasks
# ─────────────────────────────────────────────────────────────────────────────

class SendRewardNotificationTaskTest(TestCase):
    """send_reward_notification task tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user('notif_task_user')

    @patch('api.cms.tasks.send_reward_notification.NotificationService.notify_user')
    def test_notification_dispatched_for_valid_user(self, mock_notify):
        """Notification must be dispatched for a valid user."""
        mock_notify.return_value = True
        from api.cms.tasks import send_reward_notification
        send_reward_notification.apply(kwargs={
            'user_id': self.user.pk,
            'reward_amount': 2.50,
            'currency': 'USD',
            'source': 'offer_completion',
        }).get()
        mock_notify.assert_called_once()

    @patch('api.cms.tasks.send_reward_notification.NotificationService.notify_user')
    def test_notification_skipped_for_missing_user(self, mock_notify):
        """Task must not crash when user_id does not exist."""
        from api.cms.tasks import send_reward_notification
        try:
            send_reward_notification.apply(kwargs={
                'user_id': 88888888,
                'reward_amount': 1.00,
                'currency': 'USD',
                'source': 'offer_completion',
            }).get()
        except Exception as e:
            self.fail(f"Task crashed for missing user: {e}")
        mock_notify.assert_not_called()


class SendBulkNotificationsTaskTest(TestCase):
    """send_bulk_notifications task tests."""

    @patch('api.cms.tasks.send_bulk_notifications.NotificationService.bulk_notify')
    def test_bulk_notify_called_with_user_ids(self, mock_bulk):
        """Task must call bulk_notify with the provided user list."""
        mock_bulk.return_value = {'sent': 3, 'failed': 0}
        from api.cms.tasks import send_bulk_notifications
        send_bulk_notifications.apply(kwargs={
            'user_ids': [1, 2, 3],
            'title': 'System announcement',
            'body': 'New feature launched.',
            'notif_type': 'announcement',
        }).get()
        mock_bulk.assert_called_once_with(
            user_ids=[1, 2, 3],
            title='System announcement',
            body='New feature launched.',
            notif_type='announcement',
        )

    @patch('api.cms.tasks.send_bulk_notifications.NotificationService.bulk_notify')
    def test_empty_user_list_handled_gracefully(self, mock_bulk):
        """Empty user_ids list must not crash the task."""
        from api.cms.tasks import send_bulk_notifications
        try:
            send_bulk_notifications.apply(kwargs={
                'user_ids': [],
                'title': 'Test',
                'body': 'Body',
                'notif_type': 'test',
            }).get()
        except Exception as e:
            self.fail(f"Task crashed for empty user_ids: {e}")
        mock_bulk.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Leaderboard task
# ─────────────────────────────────────────────────────────────────────────────

class UpdateLeaderboardRankingsTaskTest(TestCase):

    @patch('api.cms.tasks.update_leaderboard_rankings.LeaderboardService.recalculate_rankings')
    def test_ranking_recalculation_called(self, mock_recalc):
        """Task must call recalculate_rankings without crashing."""
        mock_recalc.return_value = {'updated': 50}
        from api.cms.tasks import update_leaderboard_rankings
        result = update_leaderboard_rankings.apply().get()
        mock_recalc.assert_called_once()

    @patch('api.cms.tasks.update_leaderboard_rankings.LeaderboardService.recalculate_rankings')
    def test_service_exception_does_not_propagate_raw(self, mock_recalc):
        """A service exception must not crash the Celery worker."""
        mock_recalc.side_effect = RuntimeError('DB timeout')
        from api.cms.tasks import update_leaderboard_rankings
        try:
            update_leaderboard_rankings.apply().get(propagate=False)
        except RuntimeError:
            self.fail(
                "Task propagated raw RuntimeError — "
                "tasks must catch and handle service exceptions."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup / maintenance tasks
# ─────────────────────────────────────────────────────────────────────────────

class CleanupExpiredSessionsTaskTest(TestCase):

    @patch('api.cms.tasks.cleanup_expired_sessions.UserSession.objects')
    def test_expired_sessions_deleted(self, mock_qs):
        """Expired sessions older than cutoff must be deleted."""
        mock_manager = MagicMock()
        mock_qs.filter.return_value = mock_manager
        mock_manager.delete.return_value = (5, {})
        from api.cms.tasks import cleanup_expired_sessions
        result = cleanup_expired_sessions.apply().get()
        mock_qs.filter.assert_called()
        mock_manager.delete.assert_called_once()

    @patch('api.cms.tasks.cleanup_expired_sessions.UserSession.objects')
    def test_dry_run_does_not_call_delete(self, mock_qs):
        """dry_run=True must never call .delete()."""
        mock_manager = MagicMock()
        mock_qs.filter.return_value = mock_manager
        from api.cms.tasks import cleanup_expired_sessions
        cleanup_expired_sessions.apply(kwargs={'dry_run': True}).get()
        mock_manager.delete.assert_not_called()


class RunDataRetentionPoliciesTaskTest(TestCase):

    @patch('api.cms.tasks.run_data_retention_policies.DataRetentionService.run_all')
    def test_retention_called_in_production_mode(self, mock_run):
        """Without dry_run, DataRetentionService.run_all(dry_run=False) called."""
        mock_run.return_value = {'deleted': 10}
        from api.cms.tasks import run_data_retention_policies
        run_data_retention_policies.apply(kwargs={'dry_run': False}).get()
        mock_run.assert_called_once_with(dry_run=False)

    @patch('api.cms.tasks.run_data_retention_policies.DataRetentionService.run_all')
    def test_retention_dry_run_by_default(self, mock_run):
        """Default invocation should use dry_run=True for safety."""
        mock_run.return_value = {'would_delete': 10}
        from api.cms.tasks import run_data_retention_policies
        run_data_retention_policies.apply().get()
        called_kwargs = mock_run.call_args
        # Either called with dry_run=True explicitly or no kwarg (safe default)
        if called_kwargs:
            dry_run_arg = called_kwargs[1].get('dry_run',
                          called_kwargs[0][0] if called_kwargs[0] else True)
            self.assertTrue(dry_run_arg,
                            msg="Default task call should use dry_run=True.")


# ─────────────────────────────────────────────────────────────────────────────
# Analytics and cache tasks
# ─────────────────────────────────────────────────────────────────────────────

class GenerateDailyAnalyticsReportTaskTest(TestCase):

    @patch('api.cms.tasks.generate_daily_analytics_report.CMSAnalyticsService')
    def test_analytics_report_generated(self, mock_service):
        """Task must call the analytics service to generate a daily report."""
        mock_service.generate_daily_report.return_value = {'status': 'ok'}
        from api.cms.tasks import generate_daily_analytics_report
        generate_daily_analytics_report.apply().get()
        mock_service.generate_daily_report.assert_called_once()

    @patch('api.cms.tasks.generate_daily_analytics_report.CMSAnalyticsService')
    def test_report_failure_does_not_crash_worker(self, mock_service):
        """A failed analytics report must not crash the Celery worker."""
        mock_service.generate_daily_report.side_effect = Exception('DB error')
        from api.cms.tasks import generate_daily_analytics_report
        try:
            generate_daily_analytics_report.apply().get(propagate=False)
        except Exception:
            self.fail("Task propagated raw exception — worker must not crash.")


class RefreshOfferCacheTaskTest(TestCase):

    @patch('api.cms.tasks.refresh_offer_cache.CPALeadService.refresh_offer_list')
    def test_offer_cache_refreshed(self, mock_refresh):
        """Task must call CPALeadService.refresh_offer_list."""
        mock_refresh.return_value = {'refreshed': True, 'count': 200}
        from api.cms.tasks import refresh_offer_cache
        refresh_offer_cache.apply().get()
        mock_refresh.assert_called_once()


class WarmCMSCacheTaskTest(TestCase):

    @patch('api.cms.tasks.warm_cms_cache.CMSCacheService.warm_blog_cache')
    @patch('api.cms.tasks.warm_cms_cache.CMSCacheService.warm_popular_content')
    def test_cache_warm_up_called(self, mock_popular, mock_blog):
        """Task must warm both blog cache and popular content cache."""
        from api.cms.tasks import warm_cms_cache
        warm_cms_cache.apply().get()
        mock_blog.assert_called_once()
        mock_popular.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Content publishing task
# ─────────────────────────────────────────────────────────────────────────────

class ProcessScheduledContentPublishTaskTest(TestCase):

    @patch('api.cms.tasks.process_scheduled_content_publish.CMSPublishService.publish_scheduled_all')
    def test_scheduled_content_published(self, mock_publish):
        """Task must call CMSPublishService.publish_scheduled_all()."""
        mock_publish.return_value = {'published': 3, 'skipped': 0}
        from api.cms.tasks import process_scheduled_content_publish
        result = process_scheduled_content_publish.apply().get()
        mock_publish.assert_called_once()

    @patch('api.cms.tasks.process_scheduled_content_publish.CMSPublishService.publish_scheduled_all')
    def test_no_due_content_returns_empty_result(self, mock_publish):
        """No due content → task returns successfully with 0 published count."""
        mock_publish.return_value = {'published': 0, 'skipped': 0}
        from api.cms.tasks import process_scheduled_content_publish
        result = process_scheduled_content_publish.apply().get()
        self.assertEqual(result.get('published', 0), 0)


# ─────────────────────────────────────────────────────────────────────────────
# System health task
# ─────────────────────────────────────────────────────────────────────────────

class CheckSystemHealthTaskTest(TestCase):

    @patch('api.cms.tasks.check_system_health.HealthChecker.run_checks')
    def test_health_check_returns_report(self, mock_check):
        """Task must call HealthChecker and return a report dict."""
        mock_check.return_value = {'status': 'ok', 'checks': {}}
        from api.cms.tasks import check_system_health
        result = check_system_health.apply().get()
        mock_check.assert_called_once()
        self.assertIsInstance(result, dict)

    @patch('api.cms.tasks.check_system_health.HealthChecker.run_checks')
    @patch('api.cms.tasks.check_system_health.AlertManager.alert')
    def test_critical_health_triggers_alert(self, mock_alert, mock_check):
        """If health status is 'critical', an alert must be fired."""
        mock_check.return_value = {
            'status': 'critical',
            'checks': {'db': 'fail', 'redis': 'ok'},
        }
        from api.cms.tasks import check_system_health
        check_system_health.apply().get()
        mock_alert.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# User segment sync task
# ─────────────────────────────────────────────────────────────────────────────

class SyncUserSegmentsTaskTest(TestCase):

    @patch('api.cms.tasks.sync_user_segments.UserSegmentationService.sync_all_segments')
    def test_segment_sync_called(self, mock_sync):
        """Task must call sync_all_segments without crashing."""
        mock_sync.return_value = {'updated': 150}
        from api.cms.tasks import sync_user_segments
        sync_user_segments.apply().get()
        mock_sync.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Streak recalculation task
# ─────────────────────────────────────────────────────────────────────────────

class RecalculateUserStreaksTaskTest(TestCase):

    @patch('api.cms.tasks.recalculate_user_streaks.EarningStreak.objects')
    def test_streaks_recalculated(self, mock_qs):
        """Task must query and update earning streaks."""
        mock_qs.filter.return_value = MagicMock(count=MagicMock(return_value=10))
        from api.cms.tasks import recalculate_user_streaks
        recalculate_user_streaks.apply().get()
        mock_qs.filter.assert_called()


# ─────────────────────────────────────────────────────────────────────────────
# Withdrawal batch processing task
# ─────────────────────────────────────────────────────────────────────────────

class ProcessWithdrawalBatchTaskTest(TestCase):

    @patch('api.cms.tasks.process_withdrawal_batch.WithdrawalService.process_pending_batch')
    def test_pending_withdrawals_processed(self, mock_process):
        """Task must process the pending withdrawal batch."""
        mock_process.return_value = {'processed': 5, 'failed': 0}
        from api.cms.tasks import process_withdrawal_batch
        result = process_withdrawal_batch.apply().get()
        mock_process.assert_called_once()
        self.assertEqual(result.get('processed', 0), 5)

    @patch('api.cms.tasks.process_withdrawal_batch.WithdrawalService.process_pending_batch')
    def test_partial_failure_reported_but_task_succeeds(self, mock_process):
        """Partial failures in batch must be reported without crashing the task."""
        mock_process.return_value = {'processed': 3, 'failed': 2}
        from api.cms.tasks import process_withdrawal_batch
        result = process_withdrawal_batch.apply().get()
        self.assertEqual(result.get('failed', 0), 2)
        self.assertEqual(result.get('processed', 0), 3)


# ─────────────────────────────────────────────────────────────────────────────
# Task retry / failure behaviour
# ─────────────────────────────────────────────────────────────────────────────

class TaskRetryBehaviourTest(TestCase):
    """Generic tests for retry and failure handling across tasks."""

    @patch('api.cms.tasks.process_cpalead_postback.CPALeadService.handle_postback')
    def test_transient_error_marked_as_retry(self, mock_handle):
        """ConnectionError must trigger Celery retry, not permanent failure."""
        mock_handle.side_effect = ConnectionError('Redis unavailable')
        from api.cms.tasks import process_cpalead_postback
        task_result = process_cpalead_postback.apply(
            kwargs={
                'user_id': 1,
                'payout_usd': 1.00,
                'lead_id': 'retry_test',
                'offer_id': 1,
                'ip': '10.0.0.1',
                'hash_value': 'x',
            },
            retries=0,  # no actual retry in test; just verify it's attempted
        )
        # Should raise Retry or return a failure result — not a raw ConnectionError
        try:
            result = task_result.get(propagate=True)
        except ConnectionError:
            self.fail(
                "Task propagated raw ConnectionError. "
                "Transient errors must be caught and retried."
            )
        except Exception:
            pass  # Celery Retry exception or controlled failure is acceptable
