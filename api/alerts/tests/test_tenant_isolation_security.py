"""
Regression tests for multi-tenant isolation.

These use REAL tenants.Tenant rows (the FK target of every ``tenant`` column), so the
database actually enforces the relation. The older isolation tests in
test_track_e_service_errors_and_tenant.py swallow their own failures and cannot catch
a broken tenant FK.
"""
import datetime
import uuid

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.viewsets import ModelViewSet

from api.alerts.mixins import TenantIsolationMixin
from api.alerts.models.core import AlertRule

User = get_user_model()


def make_tenant(label):
    """Create a tenants.Tenant whatever extra required fields the host project defines."""
    Tenant = apps.get_model('tenants', 'Tenant')
    values = {}
    for field in Tenant._meta.concrete_fields:
        if field.primary_key or field.null or field.has_default():
            continue
        if getattr(field, 'auto_now', False) or getattr(field, 'auto_now_add', False):
            continue
        kind = field.get_internal_type()
        unique_text = f'{label}-{uuid.uuid4().hex[:8]}'
        if kind in ('CharField', 'TextField', 'SlugField'):
            values[field.name] = unique_text[:field.max_length] if getattr(field, 'max_length', None) else unique_text
        elif kind in ('EmailField',):
            values[field.name] = f'{unique_text}@example.com'
        elif kind in ('IntegerField', 'BigIntegerField', 'PositiveIntegerField', 'SmallIntegerField'):
            values[field.name] = 1
        elif kind == 'BooleanField':
            values[field.name] = True
        elif kind == 'DateTimeField':
            values[field.name] = timezone.now()
        elif kind == 'DateField':
            values[field.name] = datetime.date.today()
        elif kind == 'UUIDField':
            values[field.name] = uuid.uuid4()
        elif kind == 'JSONField':
            values[field.name] = {}
        else:
            raise unittest_skip(f'tenants.Tenant has a required {kind} field "{field.name}" this test cannot fill')
    return Tenant.objects.create(**values)


def unittest_skip(reason):
    import unittest
    return unittest.SkipTest(reason)


def make_rule(name, tenant=None, user=None):
    return AlertRule.objects.create(
        name=name, alert_type='server_error', severity='high', threshold_value=80.0,
        time_window_minutes=60, cooldown_minutes=30, created_by=user, tenant=tenant)


def _view_for(user, header=None):
    class _RuleViewSet(TenantIsolationMixin, ModelViewSet):
        queryset = AlertRule.objects.all()
        serializer_class = None

    request = APIRequestFactory().get('/rules/', **({'HTTP_X_TENANT_ID': header} if header else {}))
    request.user = user
    view = _RuleViewSet()
    view.request = request
    view.kwargs = {}
    view.format_kwarg = None
    return view


class TenantResolutionTest(TestCase):
    """Who may choose the tenant, and what happens when none can be resolved."""

    def setUp(self):
        self.tenant_a = make_tenant('a')
        self.tenant_b = make_tenant('b')
        self.rule_a = make_rule('Rule A', self.tenant_a)
        self.rule_b = make_rule('Rule B', self.tenant_b)

    def _user(self, name, **attrs):
        user = User.objects.create_user(username=name, email=f'{name}@example.com', password='x')
        for key, value in attrs.items():
            setattr(user, key, value)
        return user

    def test_regular_user_cannot_pick_a_tenant_with_the_header(self):
        user = self._user('plain')
        self.assertIsNone(_view_for(user, header=str(self.tenant_b.pk)).get_tenant_id())

    def test_header_cannot_override_the_users_own_tenant(self):
        user = self._user('scoped', tenant_id=self.tenant_a.pk)
        self.assertEqual(_view_for(user, header=str(self.tenant_b.pk)).get_tenant_id(), self.tenant_a.pk)

    def test_superuser_without_tenant_may_use_the_header(self):
        user = User.objects.create_superuser(username='root', email='root@example.com', password='x')
        self.assertEqual(_view_for(user, header=str(self.tenant_b.pk)).get_tenant_id(), self.tenant_b.pk)

    def test_service_account_may_use_the_header(self):
        user = self._user('svc', is_service_account=True)
        self.assertEqual(_view_for(user, header=str(self.tenant_b.pk)).get_tenant_id(), self.tenant_b.pk)

    def test_garbage_header_is_ignored(self):
        user = self._user('svc2', is_service_account=True)
        self.assertIsNone(_view_for(user, header='not-a-number').get_tenant_id())

    def test_regular_user_without_tenant_header_cannot_read_other_tenants(self):
        """With the header ignored AND multi-tenant enforced the user sees nothing."""
        user = self._user('plain2')
        with override_settings(ENABLE_MULTI_TENANT=True):
            ids = list(_view_for(user, header=str(self.tenant_b.pk)).get_queryset().values_list('id', flat=True))
        self.assertEqual(ids, [])

    def test_default_single_tenant_mode_is_unchanged(self):
        user = self._user('plain3')
        ids = set(_view_for(user).get_queryset().values_list('id', flat=True))
        self.assertEqual(ids, {self.rule_a.id, self.rule_b.id})

    def test_superuser_without_tenant_still_sees_everything_when_enforced(self):
        user = User.objects.create_superuser(username='root2', email='root2@example.com', password='x')
        with override_settings(ENABLE_MULTI_TENANT=True):
            ids = set(_view_for(user).get_queryset().values_list('id', flat=True))
        self.assertEqual(ids, {self.rule_a.id, self.rule_b.id})

    def test_scoped_user_sees_only_their_tenant(self):
        user = self._user('scoped2', tenant_id=self.tenant_a.pk)
        ids = list(_view_for(user).get_queryset().values_list('id', flat=True))
        self.assertEqual(ids, [self.rule_a.id])


class TenantIsolationApiTest(TestCase):
    """End to end through the router: list, retrieve, update, delete and create."""

    def setUp(self):
        self.tenant_a = make_tenant('api-a')
        self.tenant_b = make_tenant('api-b')
        self.user_a = User.objects.create_superuser(username='ta_admin', email='ta@example.com', password='x')
        self.user_a.tenant_id = self.tenant_a.pk  # scoped, but with every permission
        self.rule_a = make_rule('API Rule A', self.tenant_a, self.user_a)
        self.rule_b = make_rule('API Rule B', self.tenant_b)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user_a)

    @staticmethod
    def _ids(data):
        rows = data.get('results', data) if isinstance(data, dict) else data
        return {row['id'] for row in rows}

    def test_list_contains_only_own_tenant(self):
        resp = self.client.get('/rules/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._ids(resp.data), {self.rule_a.id})

    def test_other_tenants_object_is_404_for_every_verb(self):
        url = f'/rules/{self.rule_b.id}/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {'name': 'hijacked'}, format='json').status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.rule_b.refresh_from_db()
        self.assertEqual(self.rule_b.name, 'API Rule B')

    def test_own_object_is_reachable(self):
        self.assertEqual(self.client.get(f'/rules/{self.rule_a.id}/').status_code, 200)

    def test_spoofed_tenant_header_does_not_widen_access(self):
        resp = self.client.get('/rules/', HTTP_X_TENANT_ID=str(self.tenant_b.pk))
        self.assertEqual(self._ids(resp.data), {self.rule_a.id})

    def test_created_rule_is_stamped_with_callers_tenant(self):
        payload = {'name': 'Created via API', 'alert_type': 'server_error', 'severity': 'high',
                   'threshold_value': 80.0, 'time_window_minutes': 60, 'cooldown_minutes': 30}
        resp = self.client.post('/rules/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        created = AlertRule.objects.get(pk=resp.data['id'])
        self.assertEqual(created.tenant_id, self.tenant_a.pk)

    def test_client_cannot_create_into_another_tenant(self):
        payload = {'name': 'Cross tenant create', 'alert_type': 'server_error', 'severity': 'high',
                   'threshold_value': 80.0, 'time_window_minutes': 60, 'cooldown_minutes': 30,
                   'tenant': self.tenant_b.pk, 'tenant_id': self.tenant_b.pk}
        resp = self.client.post('/rules/', payload, format='json')
        if resp.status_code == 201:
            created = AlertRule.objects.get(pk=resp.data['id'])
            self.assertEqual(created.tenant_id, self.tenant_a.pk)
        else:
            self.assertIn(resp.status_code, (400, 403))
        self.assertFalse(AlertRule.objects.filter(name='Cross tenant create', tenant=self.tenant_b).exists())
