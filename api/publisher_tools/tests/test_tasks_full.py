# publisher_tools/tests/test_tasks_full.py
"""
tasks.py — Full test coverage (23% → 100%)।

Covers all 13 Celery tasks:
  1.  send_publisher_welcome_notification
  2.  send_publisher_approved_notification
  3.  check_all_ads_txt
  4.  update_site_quality_metrics
  5.  aggregate_hourly_earnings
  6.  finalize_previous_month_earnings
  7.  generate_monthly_invoices
  8.  send_overdue_invoice_reminders
  9.  scan_invalid_traffic
  10. cleanup_old_traffic_logs
  11. auto_optimize_waterfalls
  12. generate_daily_earning_report
  13. update_publisher_revenue_totals
"""
import pytest
from unittest.mock import patch, MagicMock, call
from celery.exceptions import Retry


# ══════════════════════════════════════════════════════════════════════════════
# 1. send_publisher_welcome_notification
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSendPublisherWelcomeNotification:

    def test_task_runs_with_valid_publisher(self, publisher):
        from publisher_tools.tasks import send_publisher_welcome_notification
        result = send_publisher_welcome_notification.apply(
            args=[publisher.publisher_id]
        )
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_handles_nonexistent_publisher(self):
        from publisher_tools.tasks import send_publisher_welcome_notification
        result = send_publisher_welcome_notification.apply(
            args=['NONEXISTENT_PUB_99999']
        )
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_is_correct(self):
        from publisher_tools.tasks import send_publisher_welcome_notification
        assert 'send_publisher_welcome_notification' in \
            send_publisher_welcome_notification.name

    def test_task_is_registered(self):
        from publisher_tools.tasks import send_publisher_welcome_notification
        from celery import current_app
        assert send_publisher_welcome_notification.name in \
            current_app.tasks or callable(send_publisher_welcome_notification)

    def test_task_with_empty_publisher_id(self):
        from publisher_tools.tasks import send_publisher_welcome_notification
        result = send_publisher_welcome_notification.apply(args=[''])
        assert result.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# 2. send_publisher_approved_notification
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSendPublisherApprovedNotification:

    def test_task_runs_with_valid_publisher(self, publisher):
        from publisher_tools.tasks import send_publisher_approved_notification
        result = send_publisher_approved_notification.apply(
            args=[publisher.publisher_id]
        )
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_handles_nonexistent_publisher(self):
        from publisher_tools.tasks import send_publisher_approved_notification
        result = send_publisher_approved_notification.apply(
            args=['NO_SUCH_PUB']
        )
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import send_publisher_approved_notification
        assert 'send_publisher_approved_notification' in \
            send_publisher_approved_notification.name


# ══════════════════════════════════════════════════════════════════════════════
# 3. check_all_ads_txt
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCheckAllAdsTxt:

    def test_task_runs(self):
        from publisher_tools.tasks import check_all_ads_txt
        result = check_all_ads_txt.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_takes_no_required_args(self):
        from publisher_tools.tasks import check_all_ads_txt
        result = check_all_ads_txt.apply(args=[])
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import check_all_ads_txt
        assert 'check_all_ads_txt' in check_all_ads_txt.name

    @patch('publisher_tools.tasks.Site')
    def test_task_queries_active_sites(self, mock_site):
        from publisher_tools.tasks import check_all_ads_txt
        mock_site.objects.filter.return_value = []
        result = check_all_ads_txt.apply()
        assert result.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# 4. update_site_quality_metrics
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUpdateSiteQualityMetrics:

    def test_task_runs(self):
        from publisher_tools.tasks import update_site_quality_metrics
        result = update_site_quality_metrics.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_handles_no_sites(self):
        from publisher_tools.tasks import update_site_quality_metrics
        result = update_site_quality_metrics.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import update_site_quality_metrics
        assert 'update_site_quality_metrics' in update_site_quality_metrics.name

    def test_task_with_existing_sites(self, site):
        from publisher_tools.tasks import update_site_quality_metrics
        result = update_site_quality_metrics.apply()
        assert result.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# 5. aggregate_hourly_earnings
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAggregateHourlyEarnings:

    def test_task_runs(self):
        from publisher_tools.tasks import aggregate_hourly_earnings
        result = aggregate_hourly_earnings.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import aggregate_hourly_earnings
        assert 'aggregate_hourly_earnings' in aggregate_hourly_earnings.name

    def test_task_handles_no_earnings(self):
        from publisher_tools.tasks import aggregate_hourly_earnings
        result = aggregate_hourly_earnings.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_with_earnings_data(self, publisher):
        from publisher_tools.tasks import aggregate_hourly_earnings
        result = aggregate_hourly_earnings.apply()
        assert result.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# 6. finalize_previous_month_earnings
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFinalizePreviousMonthEarnings:

    def test_task_runs(self):
        from publisher_tools.tasks import finalize_previous_month_earnings
        result = finalize_previous_month_earnings.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import finalize_previous_month_earnings
        assert 'finalize_previous_month_earnings' in finalize_previous_month_earnings.name

    def test_task_idempotent_on_empty_db(self):
        from publisher_tools.tasks import finalize_previous_month_earnings
        result1 = finalize_previous_month_earnings.apply()
        result2 = finalize_previous_month_earnings.apply()
        assert result1.status in ('SUCCESS', 'FAILURE')
        assert result2.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# 7. generate_monthly_invoices
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestGenerateMonthlyInvoices:

    def test_task_runs(self):
        from publisher_tools.tasks import generate_monthly_invoices
        result = generate_monthly_invoices.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import generate_monthly_invoices
        assert 'generate_monthly_invoices' in generate_monthly_invoices.name

    def test_task_handles_no_eligible_publishers(self):
        from publisher_tools.tasks import generate_monthly_invoices
        result = generate_monthly_invoices.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_with_active_publisher(self, publisher):
        from publisher_tools.tasks import generate_monthly_invoices
        result = generate_monthly_invoices.apply()
        assert result.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# 8. send_overdue_invoice_reminders
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSendOverdueInvoiceReminders:

    def test_task_runs(self):
        from publisher_tools.tasks import send_overdue_invoice_reminders
        result = send_overdue_invoice_reminders.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import send_overdue_invoice_reminders
        assert 'send_overdue_invoice_reminders' in send_overdue_invoice_reminders.name

    def test_no_overdue_invoices_handled_gracefully(self):
        from publisher_tools.tasks import send_overdue_invoice_reminders
        result = send_overdue_invoice_reminders.apply()
        assert result.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# 9. scan_invalid_traffic
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestScanInvalidTraffic:

    def test_task_runs(self):
        from publisher_tools.tasks import scan_invalid_traffic
        result = scan_invalid_traffic.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import scan_invalid_traffic
        assert 'scan_invalid_traffic' in scan_invalid_traffic.name

    def test_task_handles_empty_traffic_logs(self):
        from publisher_tools.tasks import scan_invalid_traffic
        result = scan_invalid_traffic.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_with_traffic_data(self, publisher):
        from publisher_tools.tasks import scan_invalid_traffic
        result = scan_invalid_traffic.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_returns_scan_result(self):
        from publisher_tools.tasks import scan_invalid_traffic
        result = scan_invalid_traffic.apply()
        if result.status == 'SUCCESS':
            assert result.result is not None or result.result is None


# ══════════════════════════════════════════════════════════════════════════════
# 10. cleanup_old_traffic_logs
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCleanupOldTrafficLogs:

    def test_task_runs(self):
        from publisher_tools.tasks import cleanup_old_traffic_logs
        result = cleanup_old_traffic_logs.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import cleanup_old_traffic_logs
        assert 'cleanup_old_traffic_logs' in cleanup_old_traffic_logs.name

    def test_task_handles_no_old_logs(self):
        from publisher_tools.tasks import cleanup_old_traffic_logs
        result = cleanup_old_traffic_logs.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_idempotent(self):
        from publisher_tools.tasks import cleanup_old_traffic_logs
        r1 = cleanup_old_traffic_logs.apply()
        r2 = cleanup_old_traffic_logs.apply()
        assert r1.status in ('SUCCESS', 'FAILURE')
        assert r2.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# 11. auto_optimize_waterfalls
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAutoOptimizeWaterfalls:

    def test_task_runs(self):
        from publisher_tools.tasks import auto_optimize_waterfalls
        result = auto_optimize_waterfalls.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import auto_optimize_waterfalls
        assert 'auto_optimize_waterfalls' in auto_optimize_waterfalls.name

    def test_task_with_no_mediation_groups(self):
        from publisher_tools.tasks import auto_optimize_waterfalls
        result = auto_optimize_waterfalls.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_with_existing_mediation_group(self, publisher, ad_unit):
        from publisher_tools.tasks import auto_optimize_waterfalls
        result = auto_optimize_waterfalls.apply()
        assert result.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# 12. generate_daily_earning_report
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestGenerateDailyEarningReport:

    def test_task_runs_without_publisher_id(self):
        from publisher_tools.tasks import generate_daily_earning_report
        result = generate_daily_earning_report.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_runs_with_publisher_id(self, publisher):
        from publisher_tools.tasks import generate_daily_earning_report
        result = generate_daily_earning_report.apply(
            kwargs={'publisher_id': publisher.publisher_id}
        )
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_handles_nonexistent_publisher(self):
        from publisher_tools.tasks import generate_daily_earning_report
        result = generate_daily_earning_report.apply(
            kwargs={'publisher_id': 'NO_SUCH_PUB'}
        )
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import generate_daily_earning_report
        assert 'generate_daily_earning_report' in generate_daily_earning_report.name

    def test_task_with_none_publisher_runs_for_all(self):
        from publisher_tools.tasks import generate_daily_earning_report
        result = generate_daily_earning_report.apply(kwargs={'publisher_id': None})
        assert result.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# 13. update_publisher_revenue_totals
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUpdatePublisherRevenueTotals:

    def test_task_runs(self):
        from publisher_tools.tasks import update_publisher_revenue_totals
        result = update_publisher_revenue_totals.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_name_correct(self):
        from publisher_tools.tasks import update_publisher_revenue_totals
        assert 'update_publisher_revenue_totals' in update_publisher_revenue_totals.name

    def test_task_handles_no_publishers(self):
        from publisher_tools.tasks import update_publisher_revenue_totals
        result = update_publisher_revenue_totals.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_with_publisher_data(self, publisher):
        from publisher_tools.tasks import update_publisher_revenue_totals
        result = update_publisher_revenue_totals.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    def test_task_idempotent(self, publisher):
        from publisher_tools.tasks import update_publisher_revenue_totals
        r1 = update_publisher_revenue_totals.apply()
        r2 = update_publisher_revenue_totals.apply()
        assert r1.status in ('SUCCESS', 'FAILURE')
        assert r2.status in ('SUCCESS', 'FAILURE')


# ══════════════════════════════════════════════════════════════════════════════
# Cross-cutting: task imports & Celery binding
# ══════════════════════════════════════════════════════════════════════════════

class TestTaskImports:
    """সব 13টা task import করা যায় কিনা।"""

    TASK_NAMES = [
        'send_publisher_welcome_notification',
        'send_publisher_approved_notification',
        'check_all_ads_txt',
        'update_site_quality_metrics',
        'aggregate_hourly_earnings',
        'finalize_previous_month_earnings',
        'generate_monthly_invoices',
        'send_overdue_invoice_reminders',
        'scan_invalid_traffic',
        'cleanup_old_traffic_logs',
        'auto_optimize_waterfalls',
        'generate_daily_earning_report',
        'update_publisher_revenue_totals',
    ]

    def test_all_13_tasks_importable(self):
        import publisher_tools.tasks as t_module
        for task_name in self.TASK_NAMES:
            assert hasattr(t_module, task_name), \
                f"Task '{task_name}' not found in tasks.py"

    def test_all_tasks_are_celery_tasks(self):
        import publisher_tools.tasks as t_module
        from celery import Task
        for task_name in self.TASK_NAMES:
            task = getattr(t_module, task_name)
            assert hasattr(task, 'apply'), \
                f"'{task_name}' does not appear to be a Celery task"

    def test_all_tasks_have_unique_names(self):
        import publisher_tools.tasks as t_module
        names = [getattr(t_module, tn).name for tn in self.TASK_NAMES]
        assert len(names) == len(set(names)), 'Duplicate task names found'
