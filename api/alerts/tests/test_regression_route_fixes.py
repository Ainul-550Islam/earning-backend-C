"""
tests/test_regression_route_fixes.py

Regression tests for bugs found by the route sweep / log review.  Each test
fails on the previous code and passes now.

  * missing object      -> 404, was 500   (blanket `except Exception` swallowed Http404)
  * add_event           -> URL passes pk, method had none; **request.data collided with
                           positional args so EVERY real request raised TypeError
  * RCA pre_save        -> RootCauseAnalysis has no `internal_only` field
  * prediction post_save-> evaluate_model_accuracy.delay(pk) but the task took no args
  * create_rca_for_incidents -> filtered on a relation (`rca`) that does not exist
"""
import logging
import re

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from api.alerts.models.incident import Incident, IncidentTimeline
from api.alerts.models.intelligence import AlertPrediction, RootCauseAnalysis


def _paths_for(viewset_name, action, pk=1):
    """Every concrete URL (mount-agnostic) that maps to ViewSet.action."""
    found = []

    def walk(patterns, prefix=''):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                cb = p.callback
                cls = getattr(cb, 'cls', None)
                acts = getattr(cb, 'actions', None) or {}
                if cls is not None and cls.__name__ == viewset_name and action in acts.values():
                    route = prefix + str(p.pattern)
                    found.append('/' + re.sub(r'<(?:\w+:)?pk>', str(pk), route).lstrip('/'))

    walk(get_resolver().url_patterns)
    return found


@pytest.fixture
def client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


# ── missing object -> 404 (was 500) ──────────────────────────────────────────
@pytest.mark.django_db
@pytest.mark.parametrize('viewset,action,method', [
    ('AlertRuleViewSet', 'activate', 'post'),
    ('AlertRuleViewSet', 'statistics', 'get'),
    ('AlertLogViewSet', 'resolve', 'post'),
    ('IncidentViewSet', 'acknowledge', 'post'),
    ('OnCallScheduleViewSet', 'add_user', 'post'),
    ('IncidentPostMortemViewSet', 'approve', 'post'),
    ('ThresholdProfileViewSet', 'apply_to_config', 'post'),   # was UnboundLocalError
    ('AlertNoiseViewSet', 'test_filter', 'post'),               # was UnboundLocalError
    ('AlertCorrelationViewSet', 'predict', 'post'),             # was UnboundLocalError
])
def test_missing_object_is_404_not_500(client, viewset, action, method):
    paths = _paths_for(viewset, action, pk=987654)
    assert paths, f'no route maps to {viewset}.{action}'
    for path in paths:
        resp = getattr(client, method)(path, data={}, format='json')
        assert resp.status_code == 404, f'{method.upper()} {path} -> {resp.status_code}'


# ── add_event ────────────────────────────────────────────────────────────────
@pytest.fixture
def timeline(open_incident, admin_user):
    event_type = IncidentTimeline._meta.get_field('event_type').choices[0][0]
    return IncidentTimeline.add_event(open_incident, event_type, 'seed', 'seed event', admin_user)


def _event_type():
    return IncidentTimeline._meta.get_field('event_type').choices[0][0]


@pytest.mark.django_db
def test_add_event_via_pk_route_uses_timelines_incident(client, timeline, open_incident):
    (path,) = [p for p in _paths_for('IncidentTimelineViewSet', 'add_event', pk=timeline.pk) if f'/{timeline.pk}/' in p]
    resp = client.post(path, {'event_type': _event_type(), 'title': 'via pk', 'description': 'd'}, format='json')
    assert resp.status_code == 200, resp.content
    ev = IncidentTimeline.objects.get(pk=resp.data['event_id'])
    assert ev.incident_id == open_incident.id and ev.title == 'via pk'


@pytest.mark.django_db
def test_add_event_with_incident_id_in_body_and_extra_fields(client, open_incident):
    paths = [p for p in _paths_for('IncidentTimelineViewSet', 'add_event', pk=1)]
    path = next(p for p in paths if '/1/' not in p) if any('/1/' not in p for p in paths) else paths[0]
    body = {'incident_id': open_incident.id, 'event_type': _event_type(), 'title': 't', 'description': 'd',
            'event_data': {'k': 'v'}, 'id': 999999}                       # `id` must be ignored
    resp = client.post(path, body, format='json')
    assert resp.status_code == 200, resp.content
    ev = IncidentTimeline.objects.get(pk=resp.data['event_id'])
    assert ev.event_data == {'k': 'v'} and ev.pk != 999999


@pytest.mark.django_db
def test_add_event_validation_and_unknown_incident(client, timeline):
    (path,) = [p for p in _paths_for('IncidentTimelineViewSet', 'add_event', pk=timeline.pk) if f'/{timeline.pk}/' in p]
    assert client.post(path, {}, format='json').status_code == 400
    bad = client.post(path, {'incident_id': 987654, 'event_type': _event_type(), 'title': 't', 'description': 'd'},
                      format='json')
    assert bad.status_code == 404


# ── RCA pre_save (internal_only) ─────────────────────────────────────────────
@pytest.mark.django_db
def test_rca_save_does_not_log_signal_error(caplog):
    with caplog.at_level(logging.ERROR):
        RootCauseAnalysis.objects.create(title='rca', description='d')
    assert not [r for r in caplog.records if 'root_cause_analysis_pre_save' in r.getMessage()]


# ── prediction post_save -> evaluate_model_accuracy(pk) ──────────────────────
@pytest.mark.django_db
def test_prediction_completed_triggers_accuracy_task_without_error(caplog):
    ptype = AlertPrediction._meta.get_field('prediction_type').choices[0][0]
    pred = AlertPrediction.objects.create(name='p1', prediction_type=ptype, training_status='pending')
    with caplog.at_level(logging.ERROR):
        pred.training_status = 'completed'
        pred.save()
    assert not [r for r in caplog.records if 'alert_prediction_post_save' in r.getMessage()], \
        [r.getMessage() for r in caplog.records]


@pytest.mark.django_db
def test_evaluate_model_accuracy_can_target_one_prediction():
    from api.alerts.tasks.intelligence import evaluate_model_accuracy
    ptype = AlertPrediction._meta.get_field('prediction_type').choices[0][0]
    a = AlertPrediction.objects.create(name='a', prediction_type=ptype, training_status='completed')
    AlertPrediction.objects.create(name='b', prediction_type=ptype, training_status='completed')
    only_a = evaluate_model_accuracy(prediction_id=a.pk)
    assert [e['model_id'] for e in only_a] == [a.pk]
    assert len(evaluate_model_accuracy()) == 2


# ── automatic RCA for high-severity incidents ────────────────────────────────
@pytest.mark.django_db
def test_create_rca_for_incidents_creates_once(admin_user, caplog):
    from api.alerts.tasks.intelligence import create_rca_for_incidents
    inc = Incident.objects.create(title='sev1', description='d', severity='critical', status='open',
                                  created_by=admin_user)
    with caplog.at_level(logging.ERROR):
        assert create_rca_for_incidents() == 1
        assert create_rca_for_incidents() == 0          # already covered -> not duplicated
    assert not [r for r in caplog.records if 'create_rca_for_incidents' in r.getMessage()]
    rca = RootCauseAnalysis.objects.get()
    assert rca.related_incidents == [inc.id]


# ── admin: every add/change page must be buildable (was FieldError -> 500) ───
def _alerts_admins():
    from django.contrib import admin as dj_admin
    from api.alerts.admin import alerts_admin_site
    pkg = __name__.rsplit('.tests', 1)[0]
    for site in (dj_admin.site, alerts_admin_site):
        for model, ma in site._registry.items():
            if model.__module__.startswith(pkg):
                yield f'{site.name}:{model.__name__}', ma


@pytest.mark.django_db
def test_every_alerts_admin_form_builds(admin_user):
    from django.test import RequestFactory
    rq = RequestFactory().get('/')
    rq.user = admin_user
    bad, n = [], 0
    for tag, ma in _alerts_admins():
        n += 1
        try:
            ma.get_form(rq, None)                              # add form
            for sf in ma.get_search_fields(rq):                # search_fields must resolve too
                pass
            list(ma.get_search_results(rq, ma.model.objects.all(), 'zzz')[0])
        except Exception as exc:                               # noqa: BLE001
            bad.append(f'{tag}: {type(exc).__name__}: {str(exc)[:120]}')
    assert n >= 20, f'only {n} admins found'
    assert not bad, '\n'.join(bad)


# ── model.clean(): never AttributeError on fields that do not exist ──────────
@pytest.mark.django_db
def test_model_clean_does_not_read_missing_fields():
    from django.apps import apps
    from django.core.exceptions import ObjectDoesNotExist, ValidationError
    bad = []
    for model in apps.get_app_config('alerts').get_models():
        try:
            model().clean()
        except (ValidationError, ObjectDoesNotExist):
            pass
        except Exception as exc:                               # noqa: BLE001
            bad.append(f'{model.__name__}.clean: {type(exc).__name__}: {exc}')
    assert not bad, '\n'.join(bad)


# ── report post_save -> distribute_reports(report_id) ────────────────────────
@pytest.mark.django_db
def test_completed_auto_distribute_report_does_not_log_signal_error(admin_user, caplog):
    from datetime import timedelta
    from django.utils import timezone
    from api.alerts.models.reporting import AlertReport
    from api.alerts.tasks.reporting import distribute_reports
    report = AlertReport.objects.create(
        title='r', report_type='daily', format_type='json', status='pending', auto_distribute=True,
        start_date=timezone.now() - timedelta(days=1), end_date=timezone.now(), created_by=admin_user)
    report.status = 'completed'
    with caplog.at_level(logging.ERROR):
        report.save()
    assert not [r for r in caplog.records if 'alert_report_post_save' in r.getMessage()], \
        [r.getMessage() for r in caplog.records]
    report.refresh_from_db()
    report.status, report.generated_at = 'completed', timezone.now()
    report.save()
    assert distribute_reports(report_id=report.pk) == 1
    assert distribute_reports(report_id=987654) == 0


# ── anomaly thresholds: save -> signal -> task -> save loop ──────────────────
@pytest.mark.django_db
def test_update_anomaly_thresholds_does_not_loop(anomaly_model, caplog):
    from api.alerts.tasks.intelligence import update_anomaly_thresholds
    from api.alerts.models.intelligence import AnomalyDetectionModel
    anomaly_model.sensitivity = 0.5
    with caplog.at_level(logging.ERROR):
        anomaly_model.save()                       # fires post_save -> task (eager in tests)
        assert update_anomaly_thresholds() >= 1
    assert not [r for r in caplog.records if 'recursion' in r.getMessage().lower()], \
        [r.getMessage() for r in caplog.records][:3]
    assert AnomalyDetectionModel.objects.get(pk=anomaly_model.pk).sensitivity == 0.5


# ── intelligence cleanup task (wrong import path) ────────────────────────────
@pytest.mark.django_db
def test_cleanup_old_intelligence_data_runs(caplog):
    from api.alerts.tasks.intelligence import cleanup_old_intelligence_data
    with caplog.at_level(logging.ERROR):
        result = cleanup_old_intelligence_data()
    assert not [r for r in caplog.records if 'cleanup_old_intelligence_data' in r.getMessage()], \
        [r.getMessage() for r in caplog.records]
    assert isinstance(result, dict) and 'correlation_history_deleted' in result


# ── adaptive threshold task (min_samples) ────────────────────────────────────
@pytest.mark.django_db
def test_recalculate_adaptive_thresholds_has_no_attribute_error(caplog):
    from api.alerts.tasks.adaptive_threshold_tasks import recalculate_adaptive_thresholds
    with caplog.at_level(logging.ERROR):
        recalculate_adaptive_thresholds()
    assert not [r for r in caplog.records if 'min_samples' in r.getMessage()]


# ── fallback notifications (AlertLog.title) ──────────────────────────────────
@pytest.mark.django_db
def test_fallback_title_helper_uses_rule_name(admin_user):
    from api.alerts.integration.fallback_logic import _alert_title
    from api.alerts.models.core import AlertLog, AlertRule
    rule = AlertRule.objects.create(name='Rule X', alert_type='server_error', severity='high',
                                    threshold_value=80.0, time_window_minutes=120, cooldown_minutes=60,
                                    created_by=admin_user)
    log = AlertLog(rule=rule, trigger_value=1, threshold_value=2, message='m')
    assert _alert_title(log) == 'Rule X'
