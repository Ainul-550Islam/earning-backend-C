"""
Tests for tasks.py — all Celery async tasks.
"""
import pytest
from unittest.mock import patch, MagicMock, call
from django.utils import timezone
from datetime import timedelta

from ..models.metric_event  import MetricEvent
from ..models.log_entry     import LogEntry
from ..models.trace_span    import TraceSpan
from ..models.alert         import Alert
from ..models.health_status import HealthStatus


@pytest.mark.django_db
class TestCleanupOldTelemetryTask:
    def test_deletes_old_metrics(self):
        from ..tasks import cleanup_old_telemetry
        old_time = timezone.now() - timedelta(days=100)
        MetricEvent.objects.create(name='old', metric_type='counter', value=1.0)
        MetricEvent.objects.filter(name='old').update(timestamp=old_time)
        before = MetricEvent.objects.count()
        result = cleanup_old_telemetry()
        assert result['metrics'] >= 1
        assert MetricEvent.objects.filter(name='old').count() == 0

    def test_deletes_old_logs(self):
        from ..tasks import cleanup_old_telemetry
        old_time = timezone.now() - timedelta(days=100)
        LogEntry.objects.create(level='info', message='old log', service='svc')
        LogEntry.objects.filter(message='old log').update(timestamp=old_time)
        result = cleanup_old_telemetry()
        assert result['logs'] >= 1

    def test_deletes_old_resolved_alerts(self):
        from ..tasks import cleanup_old_telemetry
        old_time = timezone.now() - timedelta(days=100)
        Alert.objects.create(
            name='old_alert', alert_type='metric', severity='info',
            status='resolved', message='t', service='svc',
        )
        Alert.objects.filter(name='old_alert').update(triggered_at=old_time)
        result = cleanup_old_telemetry()
        assert result['alerts'] >= 1

    def test_does_not_delete_open_alerts(self):
        from ..tasks import cleanup_old_telemetry
        old_time = timezone.now() - timedelta(days=100)
        alert = Alert.objects.create(
            name='old_open_alert', alert_type='metric', severity='warning',
            status='open', message='t', service='svc',
        )
        Alert.objects.filter(pk=alert.pk).update(triggered_at=old_time)
        cleanup_old_telemetry()
        assert Alert.objects.filter(name='old_open_alert').exists()

    def test_does_not_delete_recent_records(self):
        from ..tasks import cleanup_old_telemetry
        MetricEvent.objects.create(name='new', metric_type='counter', value=1.0)
        count_before = MetricEvent.objects.filter(name='new').count()
        cleanup_old_telemetry()
        count_after  = MetricEvent.objects.filter(name='new').count()
        assert count_after == count_before

    def test_returns_deletion_counts(self):
        from ..tasks import cleanup_old_telemetry
        result = cleanup_old_telemetry()
        assert isinstance(result, dict)
        assert 'metrics' in result
        assert 'logs'    in result
        assert 'traces'  in result
        assert 'alerts'  in result


@pytest.mark.django_db
class TestRunHealthChecksTask:
    def test_runs_without_error_empty_db(self):
        from ..tasks import run_health_checks
        result = run_health_checks()
        assert isinstance(result, dict)

    def test_processes_existing_services(self):
        from ..tasks import run_health_checks
        HealthStatus.objects.create(
            service_name='api-gateway', status='healthy', health_score=100
        )
        result = run_health_checks()
        assert 'api-gateway' in result

    def test_returns_dict_of_service_statuses(self):
        from ..tasks import run_health_checks
        HealthStatus.objects.create(service_name='svc-x', status='healthy', health_score=100)
        HealthStatus.objects.create(service_name='svc-y', status='degraded', health_score=60)
        result = run_health_checks()
        assert isinstance(result, dict)
        assert len(result) >= 2


class TestFlushMetricAggregationCacheTask:
    def test_returns_ok_status(self):
        from ..tasks import flush_metric_aggregation_cache
        with patch('django.core.cache.cache.delete_pattern', MagicMock()):
            result = flush_metric_aggregation_cache()
        assert result['status'] == 'ok'

    def test_handles_missing_delete_pattern_gracefully(self):
        """Cache backends without delete_pattern should not raise."""
        from ..tasks import flush_metric_aggregation_cache
        with patch('django.core.cache.cache.delete_pattern',
                   side_effect=AttributeError("no delete_pattern")):
            result = flush_metric_aggregation_cache()
        assert result['status'] in ('ok', 'error')


class TestDeliverWebhookTask:
    def test_delivers_successfully(self):
        from ..tasks import deliver_webhook
        mock_resp = MagicMock()
        mock_resp.status = 200
        with patch('api.telemetry_observability.tasks.urlopen',
                   return_value=MagicMock(__enter__=MagicMock(return_value=mock_resp),
                                         __exit__=MagicMock(return_value=False))):
            result = deliver_webhook('https://example.com/hook', {'event': 'test'})
        assert result['status'] == 'delivered'

    def test_adds_hmac_signature_when_secret_set(self):
        from ..tasks import deliver_webhook
        captured = []

        def fake_urlopen(req, timeout=10):
            captured.append(dict(req.headers))
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=MagicMock(status=200))
            m.__exit__  = MagicMock(return_value=False)
            return m

        with patch('api.telemetry_observability.tasks.urlopen', side_effect=fake_urlopen):
            deliver_webhook('https://example.com/hook', {'event': 'x'}, secret='my-secret')

        headers = {k.lower(): v for k, v in captured[0].items()}
        assert 'x-telemetry-signature' in headers

    def test_raises_on_max_retries(self):
        from ..tasks import deliver_webhook
        from urllib.error import URLError

        task_mock = MagicMock()
        task_mock.retry = MagicMock(side_effect=Exception("max retries exceeded"))

        with patch('api.telemetry_observability.tasks.urlopen',
                   side_effect=URLError("refused")), \
             pytest.raises(Exception):
            deliver_webhook.run('https://example.com/hook', {})


@pytest.mark.django_db
class TestAggregateAlertsTask:
    def test_auto_resolves_stale_open_alerts(self):
        from ..tasks import aggregate_alerts
        old_time = timezone.now() - timedelta(hours=25)
        alert = Alert.objects.create(
            name='stale', alert_type='metric', severity='info',
            status='open', message='stale test', service='svc',
        )
        Alert.objects.filter(pk=alert.pk).update(triggered_at=old_time)
        result = aggregate_alerts()
        assert result['auto_resolved'] >= 1
        alert.refresh_from_db()
        assert alert.status == 'resolved'

    def test_does_not_resolve_recent_alerts(self):
        from ..tasks import aggregate_alerts
        alert = Alert.objects.create(
            name='recent', alert_type='metric', severity='warning',
            status='open', message='recent', service='svc',
        )
        result = aggregate_alerts()
        alert.refresh_from_db()
        assert alert.status == 'open'

    def test_returns_count_dict(self):
        from ..tasks import aggregate_alerts
        result = aggregate_alerts()
        assert isinstance(result, dict)
        assert 'auto_resolved' in result


# ── check_internet_connectivity task ─────────────────────────────────────────

@pytest.mark.django_db
class TestCheckInternetConnectivityTask:
    """
    Tests for check_internet_connectivity.
    Network I/O mocked via InternetCheckService; only DB side-effects are real.
    """

    def _make_result(self, reachable=True, score=100, error_count=0, latency=25.0, n_probes=2):
        from ..services.internet_check_service import InternetCheckResult, ProbeResult
        probes = [
            ProbeResult('tcp', '8.8.8.8:53', i >= error_count, latency_ms=latency)
            for i in range(n_probes)
        ]
        return InternetCheckResult(
            reachable=reachable,
            health_score=score,
            probes=probes,
            avg_latency_ms=latency if reachable else None,
            error_count=error_count,
        )

    # ── Basic execution ────────────────────────────────────────────────────────

    def test_returns_dict_when_internet_reachable(self):
        from ..tasks import check_internet_connectivity
        result = self._make_result(reachable=True, score=100)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            out = check_internet_connectivity()
        assert isinstance(out, dict)
        assert out['reachable'] is True
        assert out['health_score'] == 100

    def test_returns_dict_when_internet_unreachable(self):
        from ..tasks import check_internet_connectivity
        result = self._make_result(reachable=False, score=0, error_count=2)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            out = check_internet_connectivity()
        assert out['reachable'] is False

    def test_returns_probe_counts(self):
        from ..tasks import check_internet_connectivity
        result = self._make_result(reachable=True, score=100, n_probes=5, error_count=0)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            out = check_internet_connectivity()
        assert out['probes_total'] == 5
        assert out['probes_passed'] == 5

    # ── HealthStatus persistence ───────────────────────────────────────────────

    def test_creates_health_status_record(self):
        from ..tasks import check_internet_connectivity
        from ..models.health_status import HealthStatus
        result = self._make_result(reachable=True, score=100)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        assert HealthStatus.objects.filter(
            service_name='internet', component_name='connectivity'
        ).exists()

    def test_health_status_score_matches_result(self):
        from ..tasks import check_internet_connectivity
        from ..models.health_status import HealthStatus
        result = self._make_result(reachable=True, score=80)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        record = HealthStatus.objects.get(service_name='internet', component_name='connectivity')
        assert record.health_score == 80

    def test_health_status_healthy_when_score_80_plus(self):
        from ..tasks import check_internet_connectivity
        from ..models.health_status import HealthStatus
        result = self._make_result(reachable=True, score=80)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        record = HealthStatus.objects.get(service_name='internet', component_name='connectivity')
        assert record.status == 'healthy'

    def test_health_status_degraded_when_score_40_to_79(self):
        from ..tasks import check_internet_connectivity
        from ..models.health_status import HealthStatus
        result = self._make_result(reachable=True, score=60)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        record = HealthStatus.objects.get(service_name='internet', component_name='connectivity')
        assert record.status == 'degraded'

    def test_health_status_unhealthy_when_score_below_40(self):
        from ..tasks import check_internet_connectivity
        from ..models.health_status import HealthStatus
        result = self._make_result(reachable=False, score=0, error_count=2)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        record = HealthStatus.objects.get(service_name='internet', component_name='connectivity')
        assert record.status == 'unhealthy'

    def test_upserts_not_duplicates_health_status(self):
        from ..tasks import check_internet_connectivity
        from ..models.health_status import HealthStatus
        result = self._make_result(reachable=True, score=100)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
            check_internet_connectivity()
        count = HealthStatus.objects.filter(
            service_name='internet', component_name='connectivity'
        ).count()
        assert count == 1

    # ── Alert lifecycle ────────────────────────────────────────────────────────

    def test_opens_alert_when_unreachable(self):
        from ..tasks import check_internet_connectivity
        from ..models.alert import Alert
        result = self._make_result(reachable=False, score=0, error_count=2)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        assert Alert.objects.filter(
            name='internet-connectivity-failure', status='open'
        ).exists()

    def test_does_not_duplicate_open_alert(self):
        from ..tasks import check_internet_connectivity
        from ..models.alert import Alert
        result = self._make_result(reachable=False, score=0, error_count=2)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
            check_internet_connectivity()
        count = Alert.objects.filter(
            name='internet-connectivity-failure', status='open'
        ).count()
        assert count == 1

    def test_critical_alert_when_score_is_zero(self):
        from ..tasks import check_internet_connectivity
        from ..models.alert import Alert
        result = self._make_result(reachable=False, score=0, error_count=2)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        alert = Alert.objects.get(name='internet-connectivity-failure')
        assert alert.severity == 'critical'

    def test_warning_alert_when_partially_degraded(self):
        from ..tasks import check_internet_connectivity
        from ..models.alert import Alert
        result = self._make_result(reachable=False, score=30, error_count=1, n_probes=2)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        alert = Alert.objects.get(name='internet-connectivity-failure')
        assert alert.severity == 'warning'

    def test_auto_resolves_alert_when_recovered(self):
        from ..tasks import check_internet_connectivity
        from ..models.alert import Alert
        # First: go down
        down = self._make_result(reachable=False, score=0, error_count=2)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = down
            check_internet_connectivity()
        assert Alert.objects.filter(
            name='internet-connectivity-failure', status='open'
        ).exists()
        # Then: recover
        up = self._make_result(reachable=True, score=100)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = up
            check_internet_connectivity()
        assert not Alert.objects.filter(
            name='internet-connectivity-failure', status='open'
        ).exists()

    def test_no_alert_when_reachable(self):
        from ..tasks import check_internet_connectivity
        from ..models.alert import Alert
        result = self._make_result(reachable=True, score=100)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        assert not Alert.objects.filter(
            name='internet-connectivity-failure', status='open'
        ).exists()

    # ── Metrics emission ───────────────────────────────────────────────────────

    def test_emits_health_score_metric(self):
        from ..tasks import check_internet_connectivity
        from ..models.metric_event import MetricEvent
        result = self._make_result(reachable=True, score=100, latency=18.5)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        assert MetricEvent.objects.filter(
            name='internet.connectivity.health_score', service='internet'
        ).exists()

    def test_emits_latency_metric_when_reachable(self):
        from ..tasks import check_internet_connectivity
        from ..models.metric_event import MetricEvent
        result = self._make_result(reachable=True, score=100, latency=18.5)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        assert MetricEvent.objects.filter(
            name='internet.connectivity.latency_ms', service='internet'
        ).exists()

    def test_does_not_emit_latency_metric_when_all_probes_fail(self):
        from ..tasks import check_internet_connectivity
        from ..models.metric_event import MetricEvent
        result = self._make_result(reachable=False, score=0, error_count=2, latency=None)
        with patch('api.telemetry_observability.tasks.InternetCheckService') as MockSvc:
            MockSvc.return_value.check.return_value = result
            check_internet_connectivity()
        assert not MetricEvent.objects.filter(
            name='internet.connectivity.latency_ms'
        ).exists()
