"""
alerts/conftest.py — NEWLY CREATED (was completely missing)
pytest fixtures for all alerts tests.
Without this, tests cannot share DB setup, user factories,
or test client configuration across 56 test files.

Run tests with:
    pytest alerts/tests/ -v
    pytest alerts/tests/ -v --reuse-db
    pytest alerts/tests/test_viewsets_core.py -v -k "test_activate"
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

User = get_user_model()


# The tests in this package request paths like '/incident/' and '/rules/', i.e.
# they expect the alerts URLconf mounted at the root.  Pin that for every test so
# they pass no matter where the host project mounts it (e.g. /api/alerts/).
@pytest.fixture(autouse=True)
def _alerts_root_urlconf(settings):
    settings.ROOT_URLCONF = 'api.alerts.urls'


# ── Basic users ───────────────────────────────────────────────────────────────
@pytest.fixture
def admin_user(db):
    """Superuser for admin-restricted endpoints"""
    return User.objects.create_superuser(
        username='testadmin',
        email='admin@test.alerts.com',
        password='SecureTestPass123!',
    )


@pytest.fixture
def regular_user(db):
    """Standard authenticated user"""
    return User.objects.create_user(
        username='testuser',
        email='user@test.alerts.com',
        password='SecureTestPass123!',
    )


@pytest.fixture
def second_user(db):
    """Second user for multi-user tests"""
    return User.objects.create_user(
        username='testuser2',
        email='user2@test.alerts.com',
        password='SecureTestPass123!',
    )


# ── API Clients ───────────────────────────────────────────────────────────────
@pytest.fixture
def api_client():
    """Unauthenticated DRF test client"""
    return APIClient()


@pytest.fixture
def auth_client(regular_user):
    """Authenticated DRF client (regular user)"""
    client = APIClient()
    client.force_authenticate(user=regular_user)
    return client


@pytest.fixture
def admin_client(admin_user):
    """Authenticated DRF client (admin)"""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


# ── Core model fixtures ───────────────────────────────────────────────────────
@pytest.fixture
def alert_rule(db, admin_user):
    """Standard alert rule for testing"""
    from api.alerts.models.core import AlertRule
    return AlertRule.objects.create(
        name='Test CPU Alert Rule',
        alert_type='server_error',
        severity='high',
        threshold_value=80.0,
        time_window_minutes=60,
        cooldown_minutes=30,
        is_active=True,
        created_by=admin_user,
    )


@pytest.fixture
def critical_alert_rule(db, admin_user):
    """Critical-severity alert rule"""
    from api.alerts.models.core import AlertRule
    return AlertRule.objects.create(
        name='Test Critical Alert Rule',
        alert_type='server_error',
        severity='critical',
        threshold_value=95.0,
        time_window_minutes=20,
        cooldown_minutes=10,
        is_active=True,
        created_by=admin_user,
    )


@pytest.fixture
def inactive_alert_rule(db, admin_user):
    """Inactive alert rule"""
    from api.alerts.models.core import AlertRule
    return AlertRule.objects.create(
        name='Inactive Alert Rule',
        alert_type='server_down',
        severity='medium',
        threshold_value=75.0,
        time_window_minutes=240,
        cooldown_minutes=120,
        is_active=False,
        created_by=admin_user,
    )


@pytest.fixture
def alert_log(db, alert_rule, admin_user):
    """Unresolved alert log"""
    from api.alerts.models.core import AlertLog
    return AlertLog.objects.create(
        rule=alert_rule,
        trigger_value=90.0,
        threshold_value=80.0,
        message='CPU usage at 90% — threshold exceeded',
        is_resolved=False,
    )


@pytest.fixture
def resolved_alert_log(db, alert_rule, admin_user):
    """Already-resolved alert log"""
    from api.alerts.models.core import AlertLog
    return AlertLog.objects.create(
        rule=alert_rule,
        trigger_value=85.0,
        threshold_value=80.0,
        message='CPU usage at 85% — resolved',
        is_resolved=True,
        resolved_at=timezone.now() - timedelta(hours=1),
        resolved_by=admin_user,
        resolution_note='Auto-resolved after cooldown',
    )


@pytest.fixture
def notification(db, alert_log):
    """Pending notification"""
    from api.alerts.models.core import Notification
    return Notification.objects.create(
        alert_log=alert_log,
        notification_type='email',
        status='pending',
        recipient='ops@example.com',
        message='CPU usage at 85%',
    )


# ── Channel fixtures ──────────────────────────────────────────────────────────
@pytest.fixture
def slack_channel(db):
    """Slack notification channel"""
    from api.alerts.models.channel import AlertChannel
    return AlertChannel.objects.create(
        name='Test Slack Channel',
        channel_type='slack',
        is_enabled=True,
        configuration={'webhook_url': 'https://hooks.slack.com/test'},
    )


@pytest.fixture
def email_channel(db):
    """Email notification channel"""
    from api.alerts.models.channel import AlertChannel
    return AlertChannel.objects.create(
        name='Test Email Channel',
        channel_type='email',
        is_enabled=True,
        configuration={'to': 'ops@example.com', 'from': 'alerts@example.com'},
    )


@pytest.fixture
def disabled_channel(db):
    """Disabled channel for testing enable/disable actions"""
    from api.alerts.models.channel import AlertChannel
    return AlertChannel.objects.create(
        name='Disabled Test Channel',
        channel_type='sms',
        is_enabled=False,
        configuration={'api_key': 'test'},
    )


# ── Threshold fixtures ────────────────────────────────────────────────────────
@pytest.fixture
def threshold_config(db, alert_rule):
    """Static threshold config"""
    from api.alerts.models.threshold import ThresholdConfig
    return ThresholdConfig.objects.create(
        name='Test Threshold Config',
        alert_rule=alert_rule,
        threshold_type='static',
        static_value=80.0,
        comparison_operator='gt',
        enabled=True,
    )


@pytest.fixture
def threshold_breach(db, threshold_config):
    """Open threshold breach"""
    from api.alerts.models.threshold import ThresholdBreach
    return ThresholdBreach.objects.create(
        threshold_config=threshold_config,
        breach_value=90.0,
        threshold_value=80.0,
        severity='high',
        status='open',
    )


# ── Incident fixtures ─────────────────────────────────────────────────────────
@pytest.fixture
def open_incident(db, admin_user):
    """Open incident"""
    from api.alerts.models.incident import Incident
    return Incident.objects.create(
        title='Test Production Incident',
        description='Database connections dropping',
        severity='high',
        status='open',
        created_by=admin_user,
    )


@pytest.fixture
def resolved_incident(db, admin_user):
    """Resolved incident"""
    from api.alerts.models.incident import Incident
    return Incident.objects.create(
        title='Resolved Test Incident',
        description='Was a false alarm',
        severity='low',
        status='resolved',
        created_by=admin_user,
        resolved_at=timezone.now() - timedelta(hours=2),
    )


@pytest.fixture
def on_call_schedule(db):
    """Active on-call schedule"""
    from api.alerts.models.incident import OnCallSchedule
    return OnCallSchedule.objects.create(
        name='Test On-Call Schedule',
        timezone='UTC',
        rotation_type='weekly',
        is_active=True,
    )


# ── Intelligence fixtures ─────────────────────────────────────────────────────
@pytest.fixture
def correlation(db):
    """Alert correlation"""
    from api.alerts.models.intelligence import AlertCorrelation
    return AlertCorrelation.objects.create(
        name='CPU-Memory Correlation',
        correlation_type='temporal',
        correlation_strength=0.85,
        is_active=True,
        time_window_minutes=30,
    )


@pytest.fixture
def anomaly_model(db):
    """Anomaly detection model"""
    from api.alerts.models.intelligence import AnomalyDetectionModel
    return AnomalyDetectionModel.objects.create(
        name='Test Anomaly Detector',
        detection_method='z_score',
        sensitivity=2.5,
        is_active=True,
    )


# ── Reporting fixtures ────────────────────────────────────────────────────────
@pytest.fixture
def alert_report(db, admin_user):
    """Draft alert report"""
    from api.alerts.models.reporting import AlertReport
    return AlertReport.objects.create(
        title='Weekly Test Report',
        report_type='weekly',
        status='pending',
        created_by=admin_user,
        start_date=timezone.now() - timedelta(days=7),
        end_date=timezone.now(),
    )


@pytest.fixture
def sla_breach(db):
    """Open SLA breach"""
    from api.alerts.models.reporting import SLABreach
    return SLABreach.objects.create(
        sla_name='Critical Response SLA',
        breach_type='resolution_time',
        severity='high',
        status='open',
        breached_at=timezone.now() - timedelta(hours=2),
        target_minutes=30,
        actual_minutes=150,
    )


# ── Timestamp helpers ─────────────────────────────────────────────────────────
@pytest.fixture
def now():
    return timezone.now()


@pytest.fixture
def yesterday():
    return timezone.now() - timedelta(days=1)


@pytest.fixture
def last_week():
    return timezone.now() - timedelta(days=7)
