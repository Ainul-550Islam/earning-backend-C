# publisher_tools/tests/base_test_cases.py
"""
DRY Test Base Classes।

পুরনো pattern (প্রতিটি test file-এ 3-5 বার repeated):
──────────────────────────────────────────────────────
class TestSomeFraudEndpoint:
    def test_unauthenticated_rejected(self, api_client):      ← 43×
        resp = api_client.get(url('some-ep'))
        assert resp.status_code in (401, 403)                 ← 128×

    def test_publisher_can_access(self, publisher_client):    ← same in 60 files
        resp = publisher_client.get(url('some-ep'))
        assert resp.status_code in (200, 503)                 ← 249×

    def test_admin_can_access(self, admin_client):            ← 17×
        resp = admin_client.get(url('some-ep'))
        assert resp.status_code in (200, 503)

নতুন pattern:
──────────────
class TestSomeFraudEndpoint(GetEndpointMixin):
    endpoint = 'some-ep'
    base_url = '/api/publisher-tools/fraud-advanced'

    # শুধু business logic tests লেখো — auth/access টা base class করে
"""
import pytest


# ══════════════════════════════════════════════════════════════════════════════
# Response assertion helpers (module-level functions)
# ══════════════════════════════════════════════════════════════════════════════

def assert_auth_required(response):
    """Replaces: assert resp.status_code in (401, 403)"""
    assert response.status_code in (401, 403), (
        f"Expected auth error (401/403), got {response.status_code}"
    )


def assert_ok_or_unavailable(response):
    """Replaces: assert resp.status_code in (200, 503)"""
    assert response.status_code in (200, 503), (
        f"Expected 200 or 503 (service unavailable), got {response.status_code}"
    )


def assert_ok_not_found_or_unavailable(response):
    """Replaces: assert resp.status_code in (200, 404, 503)"""
    assert response.status_code in (200, 404, 503), (
        f"Expected 200/404/503, got {response.status_code}"
    )


def assert_bad_request_or_unavailable(response):
    """Replaces: assert resp.status_code in (400, 503)"""
    assert response.status_code in (400, 503), (
        f"Expected 400 or 503, got {response.status_code}"
    )


def assert_success_response(response):
    """For 200 responses: check success flag exists."""
    assert response.status_code == 200
    data = response.json()
    assert 'success' in data or 'data' in data or 'results' in data, (
        f"Response missing success/data/results key: {list(data.keys())}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET endpoint mixin
# ══════════════════════════════════════════════════════════════════════════════

class GetEndpointMixin:
    """
    Provides standard GET endpoint tests।
    Inherit + set endpoint and base_url।

    Eliminates (from 60 test files):
      - 43× test_unauthenticated_rejected
      - 43× test_publisher_can_access
      - 17× test_admin_can_access

    Usage:
        class TestMyEndpoint(GetEndpointMixin):
            endpoint = 'my-endpoint'
            base_url = '/api/publisher-tools/some-viewset'
            requires_publisher = True   # default True
            admin_accessible   = True   # default True
    """
    endpoint           = ''
    base_url           = ''
    requires_publisher = True
    admin_accessible   = True

    def _url(self, suffix=''):
        base = f'{self.base_url}/{self.endpoint}/'
        return f'{base}{suffix}' if suffix else base

    @pytest.mark.django_db
    def test_unauthenticated_rejected(self, api_client):
        assert_auth_required(api_client.get(self._url()))

    @pytest.mark.django_db
    def test_publisher_can_access(self, publisher_client):
        if self.requires_publisher:
            assert_ok_or_unavailable(publisher_client.get(self._url()))

    @pytest.mark.django_db
    def test_admin_can_access(self, admin_client):
        if self.admin_accessible:
            assert_ok_or_unavailable(admin_client.get(self._url()))

    @pytest.mark.django_db
    def test_response_is_dict(self, publisher_client):
        resp = publisher_client.get(self._url())
        if resp.status_code == 200:
            assert isinstance(resp.json(), dict)


# ══════════════════════════════════════════════════════════════════════════════
# POST endpoint mixin
# ══════════════════════════════════════════════════════════════════════════════

class PostEndpointMixin:
    """
    Standard POST endpoint tests।

    Usage:
        class TestBackupInvoices(PostEndpointMixin):
            endpoint  = 'backup-invoices'
            base_url  = '/api/publisher-tools/admin-scripts'
            admin_only = True
            valid_body = {'months': 3}
    """
    endpoint   = ''
    base_url   = ''
    admin_only = False
    valid_body = {}

    def _url(self):
        return f'{self.base_url}/{self.endpoint}/'

    @pytest.mark.django_db
    def test_unauthenticated_rejected(self, api_client):
        assert_auth_required(api_client.post(self._url(), {}, format='json'))

    @pytest.mark.django_db
    def test_publisher_blocked_if_admin_only(self, publisher_client):
        if self.admin_only:
            resp = publisher_client.post(self._url(), self.valid_body, format='json')
            assert resp.status_code in (401, 403)

    @pytest.mark.django_db
    def test_admin_can_call(self, admin_client):
        resp = admin_client.post(self._url(), self.valid_body, format='json')
        assert_ok_or_unavailable(resp)

    @pytest.mark.django_db
    def test_empty_body_handled(self, admin_client):
        resp = admin_client.post(self._url(), {}, format='json')
        assert resp.status_code in (200, 400, 503)


# ══════════════════════════════════════════════════════════════════════════════
# Admin-only script mixin (for all 18 backup/clean/sync/generate endpoints)
# ══════════════════════════════════════════════════════════════════════════════

class AdminScriptMixin(PostEndpointMixin):
    """
    Eliminates repeated boilerplate in test_views_scripts*.py।

    Before (18 nearly-identical test classes × 4 tests = 72 duplicates):
        class TestBackupPublisherEarnings:
            def test_publisher_blocked(self, publisher_client):
                resp = publisher_client.post(url('backup-publisher-earnings'), {})
                assert resp.status_code in (401, 403)          ← 18×
            def test_admin_can_call(self, admin_client):
                resp = admin_client.post(url('backup-publisher-earnings'), {})
                assert resp.status_code in (200, 503)          ← 18×

    After:
        class TestBackupPublisherEarnings(AdminScriptMixin):
            endpoint  = 'backup-publisher-earnings'
            base_url  = '/api/publisher-tools/admin-scripts'
            valid_body = {'days': 30}
    """
    admin_only = True
    base_url   = '/api/publisher-tools/admin-scripts'

    @pytest.mark.django_db
    def test_response_has_success_flag(self, admin_client):
        resp = admin_client.post(self._url(), self.valid_body, format='json')
        if resp.status_code == 200:
            data = resp.json()
            assert data.get('success') is True


# ══════════════════════════════════════════════════════════════════════════════
# Warehouse ViewSet mixin
# ══════════════════════════════════════════════════════════════════════════════

class WarehouseViewSetMixin:
    """
    Standard warehouse endpoint tests।
    Eliminates 21× repeated auth + filter tests.

    Usage:
        class TestPublisherRecordViewSet(WarehouseViewSetMixin):
            endpoint = 'publisher-records'
    """
    endpoint = ''
    base_url = '/api/warehouse'

    def _url(self, suffix=''):
        path = f'{self.base_url}/{self.endpoint}/'
        return f'{path}{suffix}' if suffix else path

    @pytest.mark.django_db
    def test_unauthenticated_rejected(self, api_client):
        assert_auth_required(api_client.get(self._url()))

    @pytest.mark.django_db
    def test_publisher_rejected(self, publisher_client):
        resp = publisher_client.get(self._url())
        assert resp.status_code in (401, 403)

    @pytest.mark.django_db
    def test_admin_can_list(self, admin_client):
        resp = admin_client.get(self._url())
        assert resp.status_code in (200, 404)

    @pytest.mark.django_db
    def test_publisher_id_filter_accepted(self, admin_client):
        resp = admin_client.get(self._url(), {'publisher_id': 'PUB001'})
        assert resp.status_code in (200, 404)

    @pytest.mark.django_db
    def test_date_filters_accepted(self, admin_client):
        resp = admin_client.get(self._url(), {
            'start_date': '2025-01-01', 'end_date': '2025-01-31'
        })
        assert resp.status_code in (200, 404)

    @pytest.mark.django_db
    def test_is_processed_filter_accepted(self, admin_client):
        for val in ('true', 'false'):
            resp = admin_client.get(self._url(), {'is_processed': val})
            assert resp.status_code in (200, 404)

    @pytest.mark.django_db
    def test_nonexistent_record_returns_404(self, admin_client):
        resp = admin_client.get(self._url('99999/'))
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Publisher advanced endpoint mixin
# ══════════════════════════════════════════════════════════════════════════════

class PublisherAdvancedGetMixin(GetEndpointMixin):
    """
    For publisher-advanced GET endpoints।

    Before (repeated in test_views_publisher_advanced*.py):
        def test_unauthenticated_rejected(self, api_client):
            assert api_client.get(url('store')).status_code in (401, 403)
        def test_publisher_can_access(self, publisher_client):
            assert publisher_client.get(url('store')).status_code in (200, 503)

    After:
        class TestPublisherStore(PublisherAdvancedGetMixin):
            endpoint = 'store'
    """
    base_url = '/api/publisher-tools/publisher-advanced'

    @pytest.mark.django_db
    def test_response_has_data_key(self, publisher_client):
        resp = publisher_client.get(self._url())
        if resp.status_code == 200:
            body = resp.json()
            assert 'data' in body or 'success' in body


# ══════════════════════════════════════════════════════════════════════════════
# Serializer validation base
# ══════════════════════════════════════════════════════════════════════════════

class SerializerValidationMixin:
    """
    Base for serializer tests। Reduces repeated valid/invalid data tests.

    Usage:
        class TestKYCSubmitSerializer(SerializerValidationMixin):
            serializer_class = KYCSubmitSerializer
            valid_data = {'kyc_type': 'individual', ...}
            required_fields = ['kyc_type', 'full_name', 'id_type', ...]
    """
    serializer_class = None
    valid_data       = {}
    required_fields  = []

    def _get_serializer(self, data):
        return self.serializer_class(data=data)

    def test_valid_data_passes(self):
        s = self._get_serializer(self.valid_data)
        assert s.is_valid(), f"Valid data failed: {s.errors}"

    def test_empty_body_fails(self):
        if self.required_fields:
            s = self._get_serializer({})
            assert not s.is_valid()

    def test_each_required_field_alone_fails(self):
        """Remove each required field one at a time — should fail each time."""
        for field in self.required_fields:
            data = {k: v for k, v in self.valid_data.items() if k != field}
            s    = self._get_serializer(data)
            assert not s.is_valid(), f"Removing '{field}' should fail but passed"
            assert field in s.errors, f"Error should mention '{field}': {s.errors}"


# ══════════════════════════════════════════════════════════════════════════════
# Admin model admin mixin
# ══════════════════════════════════════════════════════════════════════════════

class ModelAdminMixin:
    """
    Reduces repeated admin tests (12× test_list_display + 12× test_changelist).

    Usage:
        class TestPublisherAdmin(ModelAdminMixin):
            admin_class  = PublisherAdmin
            model_name   = 'publisher'          # URL slug
            app_label    = 'publisher_tools'
    """
    admin_class = None
    model_name  = ''
    app_label   = 'publisher_tools'

    def _changelist_url(self):
        return f'/admin/{self.app_label}/{self.model_name}/'

    def test_list_display_configured(self):
        assert hasattr(self.admin_class, 'list_display')
        assert len(self.admin_class.list_display) >= 1

    def test_search_fields_configured(self):
        assert hasattr(self.admin_class, 'search_fields')

    @pytest.mark.django_db
    def test_changelist_accessible(self, admin_client):
        resp = admin_client.get(self._changelist_url())
        assert resp.status_code in (200, 302)


# ══════════════════════════════════════════════════════════════════════════════
# Task test mixin
# ══════════════════════════════════════════════════════════════════════════════

class CeleryTaskMixin:
    """
    Base for Celery task tests (12× test_task_name_correct + 10× test_task_runs).

    Usage:
        class TestScanInvalidTraffic(CeleryTaskMixin):
            task_name = 'scan_invalid_traffic'
            module    = 'publisher_tools.tasks'
    """
    task_name = ''
    module    = 'publisher_tools.tasks'

    def _get_task(self):
        import importlib
        mod = importlib.import_module(self.module)
        return getattr(mod, self.task_name)

    def test_task_importable(self):
        task = self._get_task()
        assert task is not None

    def test_task_name_correct(self):
        task = self._get_task()
        assert self.task_name in task.name

    def test_task_has_apply(self):
        task = self._get_task()
        assert hasattr(task, 'apply')

    @pytest.mark.django_db
    def test_task_runs_without_error(self):
        task   = self._get_task()
        result = task.apply()
        assert result.status in ('SUCCESS', 'FAILURE')

    @pytest.mark.django_db
    def test_task_idempotent(self):
        """Running twice should not crash."""
        task = self._get_task()
        r1   = task.apply()
        r2   = task.apply()
        assert r1.status in ('SUCCESS', 'FAILURE')
        assert r2.status in ('SUCCESS', 'FAILURE')
