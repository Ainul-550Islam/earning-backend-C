"""
Tests for Real-time Dashboard management commands.

Tests all three commands:
  - cleanup_stale_connections
  - broadcast_metrics
  - export_metrics (added in the v1.5.0 360-degree audit — the command
    existed with 91% coverage and zero tests of its own; the untested
    lines were exactly its error/edge paths: CommandError on unknown
    --ids, the "no metrics matched" warning + early return, and
    _export_csv's empty-rows guard)

Management commands are called via Django's call_command() so they execute
exactly as they would on the real system without needing a shell subprocess.
"""
import pytest
from io import StringIO
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta

from api.realtime_dashboard.models.websocket_connection import WebSocketConnection
from .fixtures import create_websocket_connection, create_real_time_metric


# ─── cleanup_stale_connections ───────────────────────────────────────────────

@pytest.mark.django_db
class TestCleanupStaleConnectionsCommand:

    def _make_stale(self, conn, hours=2):
        """Force last_ping into the past so the connection qualifies as stale."""
        WebSocketConnection.objects.filter(pk=conn.pk).update(
            last_ping=timezone.now() - timedelta(hours=hours)
        )

    def test_marks_stale_connections_as_disconnected(self):
        fresh = create_websocket_connection(connection_id='fresh', status='connected')
        stale = create_websocket_connection(connection_id='stale', status='connected')
        self._make_stale(stale, hours=2)

        out = StringIO()
        call_command('cleanup_stale_connections', '--timeout-seconds', '3600', stdout=out)

        stale.refresh_from_db()
        fresh.refresh_from_db()
        assert stale.status == 'disconnected'
        assert fresh.status == 'connected'

    def test_dry_run_does_not_update_db(self):
        stale = create_websocket_connection(connection_id='stale2', status='connected')
        self._make_stale(stale, hours=2)

        out = StringIO()
        call_command('cleanup_stale_connections', '--dry-run', stdout=out)

        stale.refresh_from_db()
        # dry-run must NOT update the DB
        assert stale.status == 'connected'
        assert 'dry-run' in out.getvalue()

    def test_dry_run_shows_correct_count(self):
        for i in range(3):
            conn = create_websocket_connection(
                connection_id=f'stale_dr_{i}', status='connected'
            )
            self._make_stale(conn, hours=2)

        out = StringIO()
        call_command('cleanup_stale_connections', '--dry-run', stdout=out)
        assert '3' in out.getvalue()

    def test_no_stale_connections_returns_zero(self):
        create_websocket_connection(connection_id='live', status='connected')
        out = StringIO()
        call_command('cleanup_stale_connections', stdout=out)
        assert '0' in out.getvalue()

    def test_custom_timeout_respected(self):
        """Connection stale by 30 min should not be cleaned with 2-hour timeout."""
        conn = create_websocket_connection(connection_id='recent', status='connected')
        WebSocketConnection.objects.filter(pk=conn.pk).update(
            last_ping=timezone.now() - timedelta(minutes=30)
        )
        call_command('cleanup_stale_connections', '--timeout-seconds', '7200')
        conn.refresh_from_db()
        assert conn.status == 'connected'


# ─── broadcast_metrics ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBroadcastMetricsCommand:

    def test_broadcasts_active_metrics(self):
        create_real_time_metric(name='CPU', status='active')
        create_real_time_metric(name='Memory', status='active')
        out = StringIO()
        # InMemoryChannelLayer is configured in tests/settings.py
        call_command('broadcast_metrics', stdout=out)
        assert '2' in out.getvalue()

    def test_dry_run_lists_metrics_without_sending(self):
        create_real_time_metric(name='Disk', status='active')
        out = StringIO()
        call_command('broadcast_metrics', '--dry-run', stdout=out)
        assert 'dry-run' in out.getvalue()
        assert 'Disk' in out.getvalue()

    def test_broadcast_specific_ids(self):
        m1 = create_real_time_metric(name='M1', status='active')
        create_real_time_metric(name='M2', status='active')
        out = StringIO()
        call_command('broadcast_metrics', '--ids', str(m1.pk), stdout=out)
        assert 'M1' in out.getvalue()
        assert 'M2' not in out.getvalue()

    def test_no_active_metrics_warns(self):
        create_real_time_metric(name='Inactive', status='inactive')
        out = StringIO()
        call_command('broadcast_metrics', stdout=out)
        assert 'No matching' in out.getvalue()

    def test_dry_run_does_not_crash_with_no_metrics(self):
        out = StringIO()
        call_command('broadcast_metrics', '--dry-run', stdout=out)
        assert 'No matching' in out.getvalue()


# ─── export_metrics ────────────────────────────────────────────────────────
# v1.5.0: this command had 0 tests despite 91% line coverage — every
# untested line was an error or edge path, never exercised in staging
# because staging never runs export_metrics against bad input.

@pytest.mark.django_db
class TestExportMetricsCommand:

    def test_export_csv_default(self):
        create_real_time_metric(name='CPU', status='active')
        out = StringIO()
        call_command('export_metrics', stdout=out)
        assert 'CPU' in out.getvalue()
        assert ',' in out.getvalue()  # CSV, not JSON

    def test_export_json_format(self):
        create_real_time_metric(name='Memory', status='active')
        out = StringIO()
        call_command('export_metrics', '--format', 'json', stdout=out)
        assert 'Memory' in out.getvalue()
        assert out.getvalue().strip().startswith('[')

    def test_export_specific_ids(self):
        m1 = create_real_time_metric(name='M1', status='active')
        create_real_time_metric(name='M2', status='active')
        out = StringIO()
        call_command('export_metrics', '--ids', str(m1.pk), stdout=out)
        assert 'M1' in out.getvalue()
        assert 'M2' not in out.getvalue()

    def test_export_unknown_id_raises_command_error(self):
        """Line 86: CommandError when a requested --ids value doesn't exist."""
        from django.core.management.base import CommandError
        with pytest.raises(CommandError, match='not found'):
            call_command('export_metrics', '--ids', '999999', stdout=StringIO())

    def test_export_no_metrics_matched_warns_and_returns(self):
        """Lines 100-101: empty queryset -> stderr warning, no CSV/JSON written."""
        create_real_time_metric(name='Active', status='active')
        out = StringIO()
        err = StringIO()
        call_command('export_metrics', '--status', 'inactive', stdout=out, stderr=err)
        assert 'No metrics matched' in err.getvalue()
        assert out.getvalue() == ''

    def test_export_status_all_includes_every_status(self):
        create_real_time_metric(name='Active', status='active')
        create_real_time_metric(name='Inactive', status='inactive')
        out = StringIO()
        call_command('export_metrics', '--status', 'all', stdout=out)
        assert 'Active' in out.getvalue()
        assert 'Inactive' in out.getvalue()

    def test_export_csv_empty_rows_guard(self):
        """
        Line 122: Command._export_csv([])'s own `if not rows: return` guard.
        Not reachable through handle() — handle() already returns before
        calling _export_csv when the queryset is empty (see
        test_export_no_metrics_matched_warns_and_returns above) — but
        _export_csv is called with self.stdout as a live Django command
        stream, so it must stay defensively correct for any future caller
        that skips that check, the same reasoning as
        utils.validate_widget_configuration's isinstance guard.
        """
        from api.realtime_dashboard.management.commands.export_metrics import Command
        command = Command()
        command.stdout = StringIO()
        # Must not raise, and must not write anything.
        command._export_csv([])
        assert command.stdout.getvalue() == ''
