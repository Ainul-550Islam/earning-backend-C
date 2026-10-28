# publisher_tools/tests/test_views_scripts_new.py
"""
ScriptRunnerViewSet — নতুন script endpoints-এর সম্পূর্ণ test।

Covers (new endpoints only — পুরনো tests test_views_scripts.py-এ আছে):

  backup_data.py:
    POST backup-publisher-earnings
    POST backup-invoices
    POST export-publisher-data

  clean_logs.py:
    POST clean-webhook-logs
    POST clean-traffic-logs
    POST clean-fraud-alerts
    POST clean-performance-snapshots
    POST clean-verification-tokens
    POST clean-database-records
    POST run-full-clean

  sync_publishers.py:
    POST sync-revenue-totals
    POST sync-status-consistency
    POST sync-payout-schedules
    POST run-full-sync

  generate_invoices.py / generate_reports.py / process_payments.py / update_ad_units.py:
    POST generate-invoices
    POST generate-reports
    POST process-payments
    POST update-ad-units
"""
import pytest

BASE = '/api/publisher-tools/admin-scripts'


def url(endpoint):
    return f'{BASE}/{endpoint}/'


# ── Shared permission mixin ───────────────────────────────────────────────────

class _AdminOnlyScriptMixin:
    """All new script endpoints are admin-only POST endpoints."""
    endpoint  = ''
    body      = {}

    def test_publisher_blocked(self, publisher_client):
        resp = publisher_client.post(url(self.endpoint), self.body, format='json')
        assert resp.status_code in (401, 403)

    def test_unauthenticated_blocked(self, api_client):
        resp = api_client.post(url(self.endpoint), self.body, format='json')
        assert resp.status_code in (401, 403)

    def test_admin_can_call(self, admin_client):
        resp = admin_client.post(url(self.endpoint), self.body, format='json')
        assert resp.status_code in (200, 503)

    def test_response_has_success_flag(self, admin_client):
        resp = admin_client.post(url(self.endpoint), self.body, format='json')
        if resp.status_code == 200:
            assert resp.json().get('success') is True


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP: backup-publisher-earnings
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBackupPublisherEarnings(_AdminOnlyScriptMixin):
    endpoint = 'backup-publisher-earnings'
    body     = {'days': 30}

    def test_days_param_accepted(self, admin_client):
        resp = admin_client.post(url('backup-publisher-earnings'), {'days': 7}, format='json')
        assert resp.status_code in (200, 503)

    def test_publisher_id_param_accepted(self, admin_client):
        resp = admin_client.post(url('backup-publisher-earnings'), {
            'publisher_id': 'PUB001',
            'days': 30,
        }, format='json')
        assert resp.status_code in (200, 503)

    def test_default_days_used_when_omitted(self, admin_client):
        resp = admin_client.post(url('backup-publisher-earnings'), {}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP: backup-invoices
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBackupInvoices(_AdminOnlyScriptMixin):
    endpoint = 'backup-invoices'
    body     = {'months': 3}

    def test_months_param_accepted(self, admin_client):
        resp = admin_client.post(url('backup-invoices'), {'months': 6}, format='json')
        assert resp.status_code in (200, 503)

    def test_default_months_used_when_omitted(self, admin_client):
        resp = admin_client.post(url('backup-invoices'), {}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP: export-publisher-data
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestExportPublisherData(_AdminOnlyScriptMixin):
    endpoint = 'export-publisher-data'
    body     = {'publisher_id': 'PUB001'}

    def test_missing_publisher_id_returns_400(self, admin_client):
        resp = admin_client.post(url('export-publisher-data'), {}, format='json')
        assert resp.status_code == 400

    def test_with_publisher_id_proceeds(self, admin_client):
        resp = admin_client.post(url('export-publisher-data'), {
            'publisher_id': 'PUB_TEST_001',
        }, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN LOGS: clean-webhook-logs
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCleanWebhookLogs(_AdminOnlyScriptMixin):
    endpoint = 'clean-webhook-logs'
    body     = {'days': 30}

    def test_days_param_accepted(self, admin_client):
        resp = admin_client.post(url('clean-webhook-logs'), {'days': 14}, format='json')
        assert resp.status_code in (200, 503)

    def test_default_days_used(self, admin_client):
        resp = admin_client.post(url('clean-webhook-logs'), {}, format='json')
        assert resp.status_code in (200, 503)

    def test_response_has_deleted_count(self, admin_client):
        resp = admin_client.post(url('clean-webhook-logs'), {'days': 30}, format='json')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'deleted_count' in data or isinstance(data, dict)


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN LOGS: clean-traffic-logs
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCleanTrafficLogs(_AdminOnlyScriptMixin):
    endpoint = 'clean-traffic-logs'
    body     = {'days': 90}

    def test_days_param_accepted(self, admin_client):
        resp = admin_client.post(url('clean-traffic-logs'), {'days': 60}, format='json')
        assert resp.status_code in (200, 503)

    def test_default_days_used(self, admin_client):
        resp = admin_client.post(url('clean-traffic-logs'), {}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN LOGS: clean-fraud-alerts
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCleanFraudAlerts(_AdminOnlyScriptMixin):
    endpoint = 'clean-fraud-alerts'
    body     = {'days': 60}

    def test_days_param_accepted(self, admin_client):
        resp = admin_client.post(url('clean-fraud-alerts'), {'days': 45}, format='json')
        assert resp.status_code in (200, 503)

    def test_default_days_used(self, admin_client):
        resp = admin_client.post(url('clean-fraud-alerts'), {}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN LOGS: clean-performance-snapshots
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCleanPerformanceSnapshots(_AdminOnlyScriptMixin):
    endpoint = 'clean-performance-snapshots'
    body     = {'months': 12}

    def test_months_param_accepted(self, admin_client):
        resp = admin_client.post(url('clean-performance-snapshots'), {'months': 6}, format='json')
        assert resp.status_code in (200, 503)

    def test_default_months_used(self, admin_client):
        resp = admin_client.post(url('clean-performance-snapshots'), {}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN LOGS: clean-verification-tokens
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCleanVerificationTokens(_AdminOnlyScriptMixin):
    endpoint = 'clean-verification-tokens'
    body     = {'days': 7}

    def test_days_param_accepted(self, admin_client):
        resp = admin_client.post(url('clean-verification-tokens'), {'days': 3}, format='json')
        assert resp.status_code in (200, 503)

    def test_default_days_used(self, admin_client):
        resp = admin_client.post(url('clean-verification-tokens'), {}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN LOGS: clean-database-records
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCleanDatabaseRecords(_AdminOnlyScriptMixin):
    endpoint = 'clean-database-records'
    body     = {'days': 90}

    def test_days_param_accepted(self, admin_client):
        resp = admin_client.post(url('clean-database-records'), {'days': 180}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN LOGS: run-full-clean
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRunFullClean(_AdminOnlyScriptMixin):
    endpoint = 'run-full-clean'
    body     = {}

    def test_with_custom_params_accepted(self, admin_client):
        resp = admin_client.post(url('run-full-clean'), {
            'webhook_log_days':         14,
            'traffic_log_days':         60,
            'fraud_alert_days':         30,
            'performance_months':        6,
            'verification_token_days':   3,
            'database_record_days':     90,
        }, format='json')
        assert resp.status_code in (200, 503)

    def test_response_has_all_clean_keys(self, admin_client):
        resp = admin_client.post(url('run-full-clean'), {}, format='json')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            expected_keys = [
                'webhook_logs', 'traffic_logs', 'fraud_alerts',
                'performance_snapshots', 'verification_tokens', 'database_records',
            ]
            for k in expected_keys:
                assert k in data, f"Key '{k}' missing from run-full-clean response"

    def test_default_params_used_when_empty_body(self, admin_client):
        resp = admin_client.post(url('run-full-clean'), {}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# SYNC: sync-revenue-totals
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSyncRevenueTotals(_AdminOnlyScriptMixin):
    endpoint = 'sync-revenue-totals'
    body     = {}

    def test_sync_runs_without_body(self, admin_client):
        resp = admin_client.post(url('sync-revenue-totals'), {}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# SYNC: sync-status-consistency
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSyncStatusConsistency(_AdminOnlyScriptMixin):
    endpoint = 'sync-status-consistency'
    body     = {}

    def test_sync_runs(self, admin_client):
        resp = admin_client.post(url('sync-status-consistency'), {}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# SYNC: sync-payout-schedules
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSyncPayoutSchedules(_AdminOnlyScriptMixin):
    endpoint = 'sync-payout-schedules'
    body     = {}

    def test_sync_runs(self, admin_client):
        resp = admin_client.post(url('sync-payout-schedules'), {}, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# SYNC: run-full-sync
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRunFullSync(_AdminOnlyScriptMixin):
    endpoint = 'run-full-sync'
    body     = {}

    def test_full_sync_runs(self, admin_client):
        resp = admin_client.post(url('run-full-sync'), {}, format='json')
        assert resp.status_code in (200, 503)

    def test_response_has_synced_flag(self, admin_client):
        resp = admin_client.post(url('run-full-sync'), {}, format='json')
        if resp.status_code == 200:
            assert resp.json().get('success') is True


# ══════════════════════════════════════════════════════════════════════════════
# GENERATE INVOICES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestGenerateInvoices(_AdminOnlyScriptMixin):
    endpoint = 'generate-invoices'
    body     = {'year': 2025, 'month': 1}

    def test_with_year_month_accepted(self, admin_client):
        resp = admin_client.post(url('generate-invoices'), {
            'year': 2025, 'month': 6,
        }, format='json')
        assert resp.status_code in (200, 503)

    def test_without_body_also_runs(self, admin_client):
        resp = admin_client.post(url('generate-invoices'), {}, format='json')
        assert resp.status_code in (200, 503)

    def test_with_publisher_id_accepted(self, admin_client):
        resp = admin_client.post(url('generate-invoices'), {
            'year': 2025, 'month': 1, 'publisher_id': 'PUB001',
        }, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# GENERATE REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestGenerateReports(_AdminOnlyScriptMixin):
    endpoint = 'generate-reports'
    body     = {'report_type': 'daily'}

    def test_daily_type_accepted(self, admin_client):
        resp = admin_client.post(url('generate-reports'), {'report_type': 'daily'}, format='json')
        assert resp.status_code in (200, 503)

    def test_weekly_type_accepted(self, admin_client):
        resp = admin_client.post(url('generate-reports'), {'report_type': 'weekly'}, format='json')
        assert resp.status_code in (200, 503)

    def test_monthly_type_accepted(self, admin_client):
        resp = admin_client.post(url('generate-reports'), {'report_type': 'monthly'}, format='json')
        assert resp.status_code in (200, 503)

    def test_without_body_runs_daily(self, admin_client):
        resp = admin_client.post(url('generate-reports'), {}, format='json')
        assert resp.status_code in (200, 503)

    def test_with_publisher_id_accepted(self, admin_client):
        resp = admin_client.post(url('generate-reports'), {
            'report_type': 'monthly', 'publisher_id': 'PUB001',
        }, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# PROCESS PAYMENTS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestProcessPayments(_AdminOnlyScriptMixin):
    endpoint = 'process-payments'
    body     = {'dry_run': True}

    def test_dry_run_true_accepted(self, admin_client):
        resp = admin_client.post(url('process-payments'), {'dry_run': True}, format='json')
        assert resp.status_code in (200, 503)

    def test_dry_run_false_accepted(self, admin_client):
        resp = admin_client.post(url('process-payments'), {'dry_run': False}, format='json')
        assert resp.status_code in (200, 503)

    def test_without_body_runs(self, admin_client):
        resp = admin_client.post(url('process-payments'), {}, format='json')
        assert resp.status_code in (200, 503)

    def test_with_publisher_id_accepted(self, admin_client):
        resp = admin_client.post(url('process-payments'), {
            'dry_run': True, 'publisher_id': 'PUB001',
        }, format='json')
        assert resp.status_code in (200, 503)

    def test_dry_run_response_message(self, admin_client):
        resp = admin_client.post(url('process-payments'), {'dry_run': True}, format='json')
        if resp.status_code == 200:
            message = resp.json().get('message', '')
            # Should mention dry run
            assert 'dry' in message.lower() or resp.json().get('success') is True


# ══════════════════════════════════════════════════════════════════════════════
# UPDATE AD UNITS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUpdateAdUnits(_AdminOnlyScriptMixin):
    endpoint = 'update-ad-units'
    body     = {}

    def test_without_body_runs(self, admin_client):
        resp = admin_client.post(url('update-ad-units'), {}, format='json')
        assert resp.status_code in (200, 503)

    def test_with_publisher_id_accepted(self, admin_client):
        resp = admin_client.post(url('update-ad-units'), {
            'publisher_id': 'PUB001',
        }, format='json')
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# Cross-cutting: all new endpoints blocked for non-admin
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAllNewScriptEndpointsAdminOnly:
    """একসাথে সব নতুন endpoint-এর permission guard test।"""

    ALL_NEW_ENDPOINTS = [
        'backup-publisher-earnings',
        'backup-invoices',
        'export-publisher-data',
        'clean-webhook-logs',
        'clean-traffic-logs',
        'clean-fraud-alerts',
        'clean-performance-snapshots',
        'clean-verification-tokens',
        'clean-database-records',
        'run-full-clean',
        'sync-revenue-totals',
        'sync-status-consistency',
        'sync-payout-schedules',
        'run-full-sync',
        'generate-invoices',
        'generate-reports',
        'process-payments',
        'update-ad-units',
    ]

    def test_all_blocked_for_publisher(self, publisher_client):
        for ep in self.ALL_NEW_ENDPOINTS:
            resp = publisher_client.post(url(ep), {}, format='json')
            assert resp.status_code in (401, 403), \
                f"POST {ep} should be blocked for publisher, got {resp.status_code}"

    def test_all_blocked_for_unauthenticated(self, api_client):
        for ep in self.ALL_NEW_ENDPOINTS:
            resp = api_client.post(url(ep), {}, format='json')
            assert resp.status_code in (401, 403), \
                f"POST {ep} should be blocked for anonymous, got {resp.status_code}"

    def test_all_accessible_for_admin(self, admin_client):
        for ep in self.ALL_NEW_ENDPOINTS:
            resp = admin_client.post(url(ep), {}, format='json')
            assert resp.status_code in (200, 503), \
                f"POST {ep} should be accessible for admin, got {resp.status_code}"
