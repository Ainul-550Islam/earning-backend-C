"""
Viewset tests for Feature Flags & A/B Testing.

FIX: the two original tests (`test_list_flags`, `test_create_flag`,
`test_list_experiments`, `test_create_experiment`) used an unauthenticated
`api_client` fixture and expected 200/201 responses. Now that auth is
correctly enforced on every endpoint (Security Blocker #1 fix), those
unauthenticated requests correctly get 401. Tests now use the
`authenticated_editor_client` fixture from conftest.py.

NEW: expanded coverage for the new endpoints added during the refactor
(clone, activate, check, rollback, request_change, approve_change,
rebalance variants, rule test/evaluate_with_stats, audit-log list,
experiment recommendations, experiment export, health check, etc.).
"""
import pytest
from rest_framework.test import APIClient

from ..models.feature_flag import FeatureFlag
from ..models.experiment import Experiment
from ..models.flag_variant import FlagVariant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_flag(name='test-flag', status='active', rollout=100, env='production', **kw):
    return FeatureFlag.objects.create(
        name=name, flag_type='boolean', status=status,
        rollout_percentage=rollout, environment=env, **kw
    )


def make_experiment(flag, name='test-exp', status='draft'):
    return Experiment.objects.create(name=name, flag=flag, status=status)


# ---------------------------------------------------------------------------
# Authentication enforcement (tests that the Security Blocker is actually fixed)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAuthEnforced:
    """Unauthenticated requests must be rejected with 401."""

    def test_flags_list_requires_auth(self):
        """Unauthenticated GET /flags/ → 401."""
        client = APIClient()
        assert client.get('/api/v1/feature-flags/flags/').status_code == 401

    def test_flags_create_requires_auth(self):
        """Unauthenticated POST /flags/ → 401."""
        client = APIClient()
        assert client.post('/api/v1/feature-flags/flags/', {}, format='json').status_code == 401

    def test_experiments_list_requires_auth(self):
        """Unauthenticated GET /experiments/ → 401."""
        client = APIClient()
        assert client.get('/api/v1/feature-flags/experiments/').status_code == 401

    def test_health_check_is_public(self):
        """Health-check endpoint must be reachable without credentials."""
        client = APIClient()
        assert client.get('/api/v1/feature-flags/health/').status_code == 200


# ---------------------------------------------------------------------------
# Feature Flag ViewSet — CRUD
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFeatureFlagViewSet:
    """Tests for FeatureFlagViewSet."""

    def test_list_flags(self, authenticated_editor_client):
        """Authenticated GET /flags/ returns 200 with paginated results."""
        make_flag('list-test-flag')
        response = authenticated_editor_client.get('/api/v1/feature-flags/flags/')
        assert response.status_code == 200
        data = response.json()
        assert 'count' in data and 'results' in data

    def test_create_flag(self, authenticated_editor_client):
        """POST /flags/ creates a flag and returns 201."""
        response = authenticated_editor_client.post(
            '/api/v1/feature-flags/flags/',
            {'name': 'new-flag', 'flag_type': 'boolean', 'status': 'draft',
             'rollout_percentage': 0, 'environment': 'production'},
            format='json'
        )
        assert response.status_code == 201
        assert response.json()['name'] == 'new-flag'
        assert FeatureFlag.objects.filter(name='new-flag').exists()

    def test_create_flag_invalid_rollout_rejected(self, authenticated_editor_client):
        """POST with rollout_percentage > 100 returns 400.
        Error is wrapped by custom_exception_handler as {'error': {...}, 'code': 400}."""
        response = authenticated_editor_client.post(
            '/api/v1/feature-flags/flags/',
            {'name': 'bad-flag', 'rollout_percentage': 150, 'environment': 'production'},
            format='json'
        )
        assert response.status_code == 400
        # custom_exception_handler wraps errors: {'error': {'rollout_percentage': [...]}, 'code': 400}
        assert 'rollout_percentage' in response.json().get('error', response.json())

    def test_create_flag_invalid_name_rejected(self, authenticated_editor_client):
        """POST with a name containing spaces returns 400."""
        response = authenticated_editor_client.post(
            '/api/v1/feature-flags/flags/',
            {'name': 'bad flag name', 'rollout_percentage': 0, 'environment': 'production'},
            format='json'
        )
        assert response.status_code == 400
        assert 'name' in response.json().get('error', response.json())

    def test_create_duplicate_name_same_environment_rejected(self, authenticated_editor_client):
        """POST with a duplicate (name, environment) pair returns 400."""
        make_flag('dup-flag', rollout=0)
        response = authenticated_editor_client.post(
            '/api/v1/feature-flags/flags/',
            {'name': 'dup-flag', 'rollout_percentage': 0, 'environment': 'production'},
            format='json'
        )
        assert response.status_code == 400

    def test_create_same_name_different_environment_allowed(self, authenticated_editor_client):
        """Same flag name is allowed in a different environment."""
        make_flag('env-flag', env='staging', rollout=0)
        response = authenticated_editor_client.post(
            '/api/v1/feature-flags/flags/',
            {'name': 'env-flag', 'rollout_percentage': 0, 'environment': 'production'},
            format='json'
        )
        assert response.status_code == 201

    def test_retrieve_flag(self, authenticated_editor_client):
        """GET /flags/{id}/ returns 200 with flag details."""
        flag = make_flag('detail-flag')
        response = authenticated_editor_client.get(f'/api/v1/feature-flags/flags/{flag.id}/')
        assert response.status_code == 200
        assert response.json()['name'] == 'detail-flag'

    def test_update_flag(self, authenticated_editor_client):
        """PATCH /flags/{id}/ updates a field."""
        flag = make_flag('update-flag', status='draft', rollout=0)
        response = authenticated_editor_client.patch(
            f'/api/v1/feature-flags/flags/{flag.id}/',
            {'rollout_percentage': 25},
            format='json'
        )
        assert response.status_code == 200
        flag.refresh_from_db()
        assert flag.rollout_percentage == 25

    def test_delete_flag(self, authenticated_admin_client):
        """DELETE /flags/{id}/ removes the flag (requires delete_flag permission → admin only)."""
        flag = make_flag('delete-flag')
        response = authenticated_admin_client.delete(f'/api/v1/feature-flags/flags/{flag.id}/')
        assert response.status_code == 204
        assert not FeatureFlag.objects.filter(id=flag.id).exists()

    def test_delete_flag_forbidden_for_editor(self, authenticated_editor_client):
        """DELETE /flags/{id}/ returns 403 for an editor (correct RBAC behaviour)."""
        flag = make_flag('delete-editor-flag')
        response = authenticated_editor_client.delete(f'/api/v1/feature-flags/flags/{flag.id}/')
        assert response.status_code == 403

    def test_filter_by_status(self, authenticated_editor_client):
        """GET /flags/?status=active returns only active flags."""
        make_flag('active-one', status='active')
        make_flag('draft-one', status='draft', rollout=0)
        response = authenticated_editor_client.get('/api/v1/feature-flags/flags/?status=active')
        assert response.status_code == 200
        names = [f['name'] for f in response.json()['results']]
        assert 'active-one' in names
        assert 'draft-one' not in names

    def test_search_by_name(self, authenticated_editor_client):
        """GET /flags/?search=checkout returns matching flags."""
        make_flag('new-checkout')
        make_flag('old-payment', rollout=0)
        response = authenticated_editor_client.get('/api/v1/feature-flags/flags/?search=checkout')
        names = [f['name'] for f in response.json()['results']]
        assert 'new-checkout' in names
        assert 'old-payment' not in names


# ---------------------------------------------------------------------------
# Feature Flag ViewSet — NEW custom actions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFeatureFlagActions:
    """Tests for custom actions added in the refactor."""

    def test_activate_action(self, authenticated_editor_client):
        """POST /flags/{id}/activate/ sets status to active."""
        flag = make_flag('action-flag', status='draft', rollout=0)
        response = authenticated_editor_client.post(
            f'/api/v1/feature-flags/flags/{flag.id}/activate/', {}, format='json'
        )
        assert response.status_code == 200
        flag.refresh_from_db()
        assert flag.status == 'active'

    def test_pause_action(self, authenticated_editor_client):
        """POST /flags/{id}/pause/ sets status to paused."""
        flag = make_flag('pause-flag')
        authenticated_editor_client.post(f'/api/v1/feature-flags/flags/{flag.id}/pause/', {}, format='json')
        flag.refresh_from_db()
        assert flag.status == 'paused'

    def test_archive_action(self, authenticated_editor_client):
        """POST /flags/{id}/archive/ sets status to archived."""
        flag = make_flag('archive-flag')
        authenticated_editor_client.post(f'/api/v1/feature-flags/flags/{flag.id}/archive/', {}, format='json')
        flag.refresh_from_db()
        assert flag.status == 'archived'

    def test_restore_action(self, authenticated_editor_client):
        """POST /flags/{id}/restore/ brings an archived flag back to draft."""
        flag = make_flag('restore-flag', status='archived', rollout=0)
        authenticated_editor_client.post(f'/api/v1/feature-flags/flags/{flag.id}/restore/', {}, format='json')
        flag.refresh_from_db()
        assert flag.status == 'draft'

    def test_check_action_enabled(self, authenticated_editor_client):
        """GET /flags/{id}/check/ returns enabled=True for a 100% rollout active flag."""
        flag = make_flag('check-flag')
        response = authenticated_editor_client.get(f'/api/v1/feature-flags/flags/{flag.id}/check/')
        assert response.status_code == 200
        assert response.json()['enabled'] is True

    def test_check_action_disabled(self, authenticated_editor_client):
        """GET /flags/{id}/check/ returns enabled=False for a paused flag."""
        flag = make_flag('check-paused', status='paused')
        response = authenticated_editor_client.get(f'/api/v1/feature-flags/flags/{flag.id}/check/')
        assert response.status_code == 200
        assert response.json()['enabled'] is False

    def test_clone_action(self, authenticated_editor_client):
        """POST /flags/clone/ creates a draft clone with 0% rollout."""
        make_flag('clone-source')
        response = authenticated_editor_client.post(
            '/api/v1/feature-flags/flags/clone/',
            {'source_name': 'clone-source', 'new_name': 'clone-dest', 'environment': 'production'},
            format='json'
        )
        assert response.status_code == 201
        clone = response.json()
        assert clone['name'] == 'clone-dest'
        assert clone['status'] == 'draft'
        assert clone['rollout_percentage'] == 0

    def test_bulk_update_action(self, authenticated_editor_client):
        """POST /flags/bulk-update/ changes status for a list of named flags."""
        make_flag('bulk-a')
        make_flag('bulk-b')
        response = authenticated_editor_client.post(
            '/api/v1/feature-flags/flags/bulk_update/',
            {'names': ['bulk-a', 'bulk-b'], 'status': 'paused'},
            format='json'
        )
        assert response.status_code == 200
        assert response.json()['updated_count'] == 2
        assert FeatureFlag.objects.filter(name__in=['bulk-a', 'bulk-b'], status='paused').count() == 2

    def test_versions_action(self, authenticated_editor_client):
        """GET /flags/{id}/versions/ returns version history."""
        flag = make_flag('versioned-flag')
        response = authenticated_editor_client.get(f'/api/v1/feature-flags/flags/{flag.id}/versions/')
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    def test_rollback_action(self, authenticated_editor_client):
        """POST /flags/{id}/rollback/ restores a flag to a previous version."""
        flag = make_flag('rollback-flag', rollout=0)
        # Update to create v2
        authenticated_editor_client.patch(
            f'/api/v1/feature-flags/flags/{flag.id}/', {'rollout_percentage': 50}, format='json'
        )
        # Roll back to version 1
        response = authenticated_editor_client.post(
            f'/api/v1/feature-flags/flags/{flag.id}/rollback/',
            {'version_number': 1},
            format='json'
        )
        assert response.status_code == 200
        flag.refresh_from_db()
        assert flag.rollout_percentage == 0

    def test_request_change_action(self, authenticated_editor_client):
        """POST /flags/{id}/request_change/ creates a pending change request."""
        flag = make_flag('change-req-flag', status='draft', rollout=0)
        response = authenticated_editor_client.post(
            f'/api/v1/feature-flags/flags/{flag.id}/request_change/',
            {'rollout_percentage': 100},
            format='json'
        )
        assert response.status_code == 201
        assert response.json()['status'] == 'pending'

    def test_approve_change_action_requires_admin(self, authenticated_editor_client, authenticated_admin_client):
        """POST /flags/{id}/approve_change/ applies the change; editor cannot do it, admin can."""
        from ..models.approval import FlagChangeRequest

        flag = make_flag('approve-flag', status='draft', rollout=0)

        # Editor creates a change request
        resp = authenticated_editor_client.post(
            f'/api/v1/feature-flags/flags/{flag.id}/request_change/',
            {'rollout_percentage': 80},
            format='json'
        )
        change_id = resp.json()['id']

        # Editor cannot approve
        resp = authenticated_editor_client.post(
            f'/api/v1/feature-flags/flags/{flag.id}/approve_change/',
            {'change_request_id': change_id},
            format='json'
        )
        assert resp.status_code == 403

        # Admin can approve
        resp = authenticated_admin_client.post(
            f'/api/v1/feature-flags/flags/{flag.id}/approve_change/',
            {'change_request_id': change_id},
            format='json'
        )
        assert resp.status_code == 200
        flag.refresh_from_db()
        assert flag.rollout_percentage == 80

    def test_schedule_action(self, authenticated_editor_client):
        """POST /flags/{id}/schedule/ creates a ScheduledChange row."""
        from ..models.scheduling import ScheduledChange

        flag = make_flag('schedule-flag', status='draft', rollout=0)
        response = authenticated_editor_client.post(
            f'/api/v1/feature-flags/flags/{flag.id}/schedule/',
            {'change_type': 'activate', 'scheduled_for': '2030-01-01T00:00:00Z'},
            format='json'
        )
        assert response.status_code == 201
        assert ScheduledChange.objects.filter(flag=flag, change_type='activate').exists()


# ---------------------------------------------------------------------------
# Experiment ViewSet
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExperimentViewSet:
    """Tests for ExperimentViewSet."""

    def test_list_experiments(self, authenticated_editor_client):
        """Authenticated GET /experiments/ returns 200."""
        flag = make_flag('exp-list-flag')
        make_experiment(flag, 'exp-list-test')
        response = authenticated_editor_client.get('/api/v1/feature-flags/experiments/')
        assert response.status_code == 200
        assert 'results' in response.json()

    def test_create_experiment(self, authenticated_editor_client):
        """POST /experiments/ creates an experiment."""
        flag = make_flag('exp-create-flag')
        response = authenticated_editor_client.post(
            '/api/v1/feature-flags/experiments/',
            {'name': 'new-experiment', 'flag': flag.id, 'status': 'draft'},
            format='json'
        )
        assert response.status_code == 201
        assert response.json()['name'] == 'new-experiment'

    def test_start_experiment(self, authenticated_editor_client):
        """POST /experiments/{id}/start/ sets status to running."""
        flag = make_flag('exp-start-flag')
        exp = make_experiment(flag, 'exp-start-test')
        response = authenticated_editor_client.post(
            f'/api/v1/feature-flags/experiments/{exp.id}/start/', {}, format='json'
        )
        assert response.status_code == 200
        exp.refresh_from_db()
        assert exp.status == 'running'

    def test_complete_experiment(self, authenticated_editor_client):
        """POST /experiments/{id}/complete/ sets status to completed."""
        flag = make_flag('exp-complete-flag')
        exp = make_experiment(flag, 'exp-complete-test', status='running')
        authenticated_editor_client.post(
            f'/api/v1/feature-flags/experiments/{exp.id}/complete/', {}, format='json'
        )
        exp.refresh_from_db()
        assert exp.status == 'completed'

    def test_recommendations_action(self, authenticated_editor_client):
        """GET /experiments/{id}/recommendations/ returns a recommendation string."""
        flag = make_flag('exp-rec-flag')
        exp = make_experiment(flag, 'exp-rec-test')
        response = authenticated_editor_client.get(
            f'/api/v1/feature-flags/experiments/{exp.id}/recommendations/'
        )
        assert response.status_code == 200
        assert 'recommendation' in response.json()

    def test_export_action(self, authenticated_editor_client):
        """GET /experiments/{id}/export/ returns a CSV response."""
        flag = make_flag('exp-export-flag')
        exp = make_experiment(flag, 'exp-export-test')
        response = authenticated_editor_client.get(
            f'/api/v1/feature-flags/experiments/{exp.id}/export/'
        )
        assert response.status_code == 200
        assert 'text/csv' in response['Content-Type']


# ---------------------------------------------------------------------------
# Variant ViewSet — NEW actions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFlagVariantViewSet:
    """Tests for FlagVariantViewSet."""

    def test_rebalance_action(self, authenticated_editor_client):
        """POST /variants/rebalance/ proportionally rescales weights to sum=100."""
        flag = make_flag('rebalance-flag')
        v1 = FlagVariant.objects.create(flag=flag, name='control', weight=30, value='A')
        v2 = FlagVariant.objects.create(flag=flag, name='treatment', weight=70, value='B')
        response = authenticated_editor_client.post(
            '/api/v1/feature-flags/variants/rebalance/',
            {'flag_id': flag.id},
            format='json'
        )
        assert response.status_code == 200
        weights = {v['name']: v['weight'] for v in response.json()['variants']}
        assert sum(weights.values()) == 100
        assert weights['control'] == 30
        assert weights['treatment'] == 70


# ---------------------------------------------------------------------------
# Rollout Rule ViewSet — NEW actions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRolloutRuleViewSet:
    """Tests for RolloutRuleViewSet new actions."""

    def _make_rule(self, flag):
        from ..models.rollout_rule import RolloutRule
        return RolloutRule.objects.create(
            flag=flag, rule_type='user_id', field='user_id',
            operator='equals', value='user-123'
        )

    def test_test_action(self, authenticated_editor_client):
        """POST /rollout-rules/{id}/test/ returns match result for context."""
        flag = make_flag('rule-flag')
        rule = self._make_rule(flag)
        response = authenticated_editor_client.post(
            f'/api/v1/feature-flags/rollout-rules/{rule.id}/test/',
            {'context': {'user_id': 'user-123'}},
            format='json'
        )
        assert response.status_code == 200
        assert 'matches' in response.json()

    def test_evaluate_with_stats_action(self, authenticated_editor_client):
        """POST /rollout-rules/{id}/evaluate_with_stats/ returns match rate."""
        flag = make_flag('rule-stats-flag')
        rule = self._make_rule(flag)
        contexts = [{'user_id': 'user-123'}, {'user_id': 'other-user'}]
        response = authenticated_editor_client.post(
            f'/api/v1/feature-flags/rollout-rules/{rule.id}/evaluate_with_stats/',
            {'contexts': contexts},
            format='json'
        )
        assert response.status_code == 200
        data = response.json()
        assert data['total_tested'] == 2
        assert 'match_percentage' in data


# ---------------------------------------------------------------------------
# Analytics ViewSet — NEW actions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalyticsViewSet:
    """Tests for FlagAnalyticsViewSet."""

    def test_portfolio_overview(self, authenticated_editor_client):
        """GET /analytics/portfolio_overview/ returns flag counts."""
        make_flag('overview-flag-a')
        make_flag('overview-flag-b', status='draft', rollout=0)
        response = authenticated_editor_client.get(
            '/api/v1/feature-flags/analytics/portfolio_overview/?environment=production'
        )
        assert response.status_code == 200
        data = response.json()
        assert 'total_flags' in data
        assert data['total_flags'] >= 2

    def test_performance_action(self, authenticated_editor_client):
        """GET /analytics/performance/?flag_id=X returns impact stats."""
        flag = make_flag('perf-flag')
        response = authenticated_editor_client.get(
            f'/api/v1/feature-flags/analytics/performance/?flag_id={flag.id}'
        )
        assert response.status_code == 200
        data = response.json()['data']
        assert 'total_evaluations' in data
        assert 'optimization_score' in data


# ---------------------------------------------------------------------------
# Audit Log ViewSet
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAuditLogViewSet:
    """Tests for AuditLogViewSet (read-only)."""

    def test_list_audit_logs(self, authenticated_editor_client):
        """GET /audit-logs/ returns paginated results."""
        make_flag('audit-flag')
        response = authenticated_editor_client.get('/api/v1/feature-flags/audit-logs/')
        assert response.status_code == 200
        assert 'count' in response.json()
        assert response.json()['count'] >= 1

    def test_audit_log_no_create(self, authenticated_admin_client):
        """POST /audit-logs/ is not allowed (read-only viewset)."""
        response = authenticated_admin_client.post('/api/v1/feature-flags/audit-logs/', {}, format='json')
        assert response.status_code == 405

    def test_audit_log_no_delete(self, authenticated_admin_client):
        """DELETE /audit-logs/ is not allowed (read-only viewset)."""
        from ..models.audit import AuditLog
        make_flag('audit-del-flag')
        log = AuditLog.objects.first()
        response = authenticated_admin_client.delete(f'/api/v1/feature-flags/audit-logs/{log.id}/')
        assert response.status_code == 405


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHealthCheck:
    """Tests for the health check endpoint."""

    def test_health_check_returns_healthy(self):
        """Health check returns {'status': 'healthy', ...} when all systems are up."""
        client = APIClient()
        response = client.get('/api/v1/feature-flags/health/')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['checks']['database'] is True
        assert data['checks']['cache'] is True

    def test_health_check_no_auth_required(self):
        """Health check must be reachable without authentication."""
        client = APIClient()
        assert client.get('/api/v1/feature-flags/health/').status_code == 200
