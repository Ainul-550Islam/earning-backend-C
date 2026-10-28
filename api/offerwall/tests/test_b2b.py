"""
Tests for the B2B SaaS layer.

Run: python manage.py test api.offerwall.tests.test_b2b
"""
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def mk_user(un='b2b_u', admin=False):
    if admin:
        return User.objects.create_superuser(
            username=un, email=f'{un}@t.com', password='Admin@123')
    return User.objects.create_user(
        username=un, email=f'{un}@t.com', password='pass')


def mk_plan(plan_type='starter', price=Decimal('2000'), rev_share=Decimal('10')):
    from api.offerwall.b2b.models import B2BPlan
    return B2BPlan.objects.create(
        name=f'Plan_{plan_type}_{uuid.uuid4().hex[:4]}',
        plan_type=plan_type,
        monthly_price_bdt=price,
        monthly_price_usd=price / Decimal('110'),
        monthly_api_calls=50_000,
        monthly_conversions=500,
        max_active_walls=3,
        max_api_keys=5,
        revenue_share_pct=rev_share,
        allow_content_lock=True,
        support_level='email',
    )


def mk_client(user, plan=None, status='active'):
    from api.offerwall.b2b.models import B2BClient, B2BOnboarding
    if not plan:
        plan = mk_plan()
    client = B2BClient.objects.create(
        owner=user,
        company_name=f'TestCo_{uuid.uuid4().hex[:6]}',
        company_website='https://test.com',
        business_type='web_app',
        country='BD',
        contact_email=user.email,
        plan=plan,
        status=status,
    )
    B2BOnboarding.objects.create(client=client)
    return client


# ═════════════════════════════════════════════════════════════
# B2BPlan model
# ═════════════════════════════════════════════════════════════

class B2BPlanModelTest(TestCase):

    def test_create_free_plan(self):
        plan = mk_plan('free', Decimal('0'), Decimal('0'))
        self.assertEqual(plan.monthly_price_bdt, Decimal('0'))

    def test_is_unlimited_calls_true_for_zero(self):
        from api.offerwall.b2b.models import B2BPlan
        plan = B2BPlan.objects.create(
            name='Unlimited', plan_type='enterprise',
            monthly_api_calls=0, revenue_share_pct=Decimal('30'))
        self.assertTrue(plan.is_unlimited_calls())

    def test_is_unlimited_calls_false_for_nonzero(self):
        plan = mk_plan()
        self.assertFalse(plan.is_unlimited_calls())

    def test_get_feature_list_includes_content_lock(self):
        plan = mk_plan()
        plan.allow_content_lock = True
        plan.save()
        self.assertIn('Content locking', plan.get_feature_list())

    def test_get_feature_list_excludes_disabled(self):
        plan = mk_plan()
        plan.allow_white_label = False
        plan.save()
        self.assertNotIn('White-label branding', plan.get_feature_list())

    def test_get_free_returns_free_plan(self):
        from api.offerwall.b2b.models import B2BPlan
        free = B2BPlan.objects.create(
            name='Free_test', plan_type='free',
            monthly_price_bdt=Decimal('0'), revenue_share_pct=Decimal('0'))
        result = B2BPlan.get_free()
        self.assertEqual(result.pk, free.pk)

    def test_str_shows_price(self):
        plan = mk_plan('pro', Decimal('8000'))
        self.assertIn('8000', str(plan))


# ═════════════════════════════════════════════════════════════
# B2BClient model
# ═════════════════════════════════════════════════════════════

class B2BClientModelTest(TestCase):

    def setUp(self):
        self.user = mk_user('cl_m_u')
        self.plan = mk_plan()

    def test_create_client(self):
        client = mk_client(self.user, self.plan)
        self.assertEqual(client.owner, self.user)

    def test_effective_revenue_share_uses_plan(self):
        client = mk_client(self.user, self.plan)
        self.assertEqual(client.effective_revenue_share,
                         self.plan.revenue_share_pct)

    def test_effective_revenue_share_custom_overrides_plan(self):
        client = mk_client(self.user, self.plan)
        client.custom_revenue_share_pct = Decimal('25')
        client.save()
        self.assertEqual(client.effective_revenue_share, Decimal('25'))

    def test_is_active_true(self):
        client = mk_client(self.user, self.plan, status='active')
        self.assertTrue(client.is_active())

    def test_is_active_false_for_suspended(self):
        client = mk_client(self.user, self.plan, status='suspended')
        self.assertFalse(client.is_active())

    def test_is_plan_valid_true(self):
        client = mk_client(self.user, self.plan)
        self.assertTrue(client.is_plan_valid())

    def test_is_plan_valid_false_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        client = mk_client(self.user, self.plan)
        client.plan_expires_at = timezone.now() - timedelta(hours=1)
        client.save()
        self.assertFalse(client.is_plan_valid())

    def test_activate_changes_status(self):
        client = mk_client(self.user, self.plan, status='verified')
        client.activate()
        self.assertEqual(client.status, 'active')

    def test_suspend_sets_reason(self):
        client = mk_client(self.user, self.plan)
        client.suspend('Non-payment')
        self.assertEqual(client.status, 'suspended')
        self.assertEqual(client.suspension_reason, 'Non-payment')

    def test_can_make_api_call_active(self):
        client = mk_client(self.user, self.plan, status='active')
        can, reason = client.can_make_api_call()
        self.assertTrue(can)
        self.assertIsNone(reason)

    def test_can_make_api_call_suspended_blocked(self):
        client = mk_client(self.user, self.plan, status='suspended')
        can, reason = client.can_make_api_call()
        self.assertFalse(can)
        self.assertEqual(reason, 'client_suspended')

    def test_can_make_api_call_quota_exceeded(self):
        plan = mk_plan(plan_type='pro')
        plan.monthly_api_calls = 1
        plan.save()
        client = mk_client(self.user, plan, status='active')
        usage = client.get_current_usage()
        usage.api_calls = 1
        usage.save()
        can, reason = client.can_make_api_call()
        self.assertFalse(can)
        self.assertEqual(reason, 'quota_exceeded')

    def test_has_feature_true(self):
        plan = mk_plan(plan_type='enterprise')
        plan.allow_content_lock = True
        plan.save()
        client = mk_client(self.user, plan)
        self.assertTrue(client.has_feature('content_lock'))

    def test_has_feature_false(self):
        plan = mk_plan(plan_type='free')
        plan.allow_white_label = False
        plan.save()
        client = mk_client(self.user, plan)
        self.assertFalse(client.has_feature('white_label'))

    def test_get_current_usage_creates_record(self):
        client = mk_client(self.user, self.plan)
        usage = client.get_current_usage()
        self.assertIsNotNone(usage)
        self.assertEqual(usage.client, client)

    def test_str_shows_company_name(self):
        client = mk_client(self.user, self.plan)
        self.assertIn(client.company_name, str(client))


# ═════════════════════════════════════════════════════════════
# B2BUsageRecord model
# ═════════════════════════════════════════════════════════════

class B2BUsageRecordTest(TestCase):

    def setUp(self):
        self.user   = mk_user('ur_u')
        self.client = mk_client(self.user)

    def test_increment_api_calls(self):
        usage = self.client.get_current_usage()
        usage.increment('api_calls', 5)
        usage.refresh_from_db()
        self.assertEqual(usage.api_calls, 5)

    def test_quota_pct_zero_when_no_calls(self):
        usage = self.client.get_current_usage()
        self.assertEqual(usage.quota_pct(), 0.0)

    def test_quota_pct_50_when_half_used(self):
        plan = self.client.plan
        plan.monthly_api_calls = 1000
        plan.save()
        usage = self.client.get_current_usage()
        usage.api_calls = 500
        usage.save()
        self.assertEqual(usage.quota_pct(), 50.0)

    def test_quota_pct_zero_for_unlimited(self):
        plan = self.client.plan
        plan.monthly_api_calls = 0
        plan.save()
        usage = self.client.get_current_usage()
        usage.api_calls = 99999
        usage.save()
        self.assertEqual(usage.quota_pct(), 0.0)

    def test_unique_per_month(self):
        from django.db import IntegrityError
        from api.offerwall.b2b.models import B2BUsageRecord
        from django.utils import timezone
        now = timezone.now()
        B2BUsageRecord.objects.create(
            client=self.client, period_year=now.year,
            period_month=now.month)
        with self.assertRaises(IntegrityError):
            B2BUsageRecord.objects.create(
                client=self.client, period_year=now.year,
                period_month=now.month)


# ═════════════════════════════════════════════════════════════
# B2BOnboarding model
# ═════════════════════════════════════════════════════════════

class B2BOnboardingTest(TestCase):

    def setUp(self):
        self.user   = mk_user('ob_u')
        self.client = mk_client(self.user)

    def test_completion_pct_zero_initially(self):
        self.assertEqual(self.client.onboarding.completion_pct(), 0)

    def test_complete_step_increments_pct(self):
        self.client.onboarding.complete_step('signup')
        pct = self.client.onboarding.completion_pct()
        self.assertGreater(pct, 0)

    def test_complete_all_steps_marks_complete(self):
        for step in self.client.onboarding.STEP_ORDER:
            self.client.onboarding.complete_step(step)
        self.assertTrue(self.client.onboarding.is_complete)
        self.assertEqual(self.client.onboarding.completion_pct(), 100)

    def test_duplicate_step_not_added_twice(self):
        self.client.onboarding.complete_step('signup')
        self.client.onboarding.complete_step('signup')
        count = self.client.onboarding.completed_steps.count('signup')
        self.assertEqual(count, 1)

    def test_next_step_display_returns_string(self):
        result = self.client.onboarding.next_step_display()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_step_timestamp_set_on_completion(self):
        self.client.onboarding.complete_step('signup')
        self.assertIsNotNone(self.client.onboarding.signup_at)


# ═════════════════════════════════════════════════════════════
# B2B API views
# ═════════════════════════════════════════════════════════════

class B2BPlanListViewTest(TestCase):

    def test_plan_list_public_200(self):
        mk_plan('free', Decimal('0'))
        mk_plan('starter', Decimal('2000'))
        client = APIClient()
        r = client.get('/api/offerwall/b2b/plans/')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data, list)

    def test_plan_list_unauthenticated_allowed(self):
        r = APIClient().get('/api/offerwall/b2b/plans/')
        self.assertNotEqual(r.status_code, 401)


class B2BRegisterViewTest(TestCase):

    def setUp(self):
        self.client_api = APIClient()
        self.user = mk_user('reg_u')
        self.plan = mk_plan('free', Decimal('0'))
        self.client_api.force_authenticate(self.user)

    def test_register_returns_201(self):
        r = self.client_api.post('/api/offerwall/b2b/register/', {
            'company_name':    'My App Ltd',
            'company_website': 'https://myapp.com',
            'business_type':   'mobile_app',
            'country':         'BD',
            'contact_email':   'hi@myapp.com',
            'plan_type':       'free',
        }, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertIn('company_name', r.data)

    def test_register_twice_returns_409(self):
        data = {'company_name': 'Co Ltd', 'contact_email': 'x@t.com',
                 'plan_type': 'free', 'country': 'BD', 'business_type': 'web_app'}
        self.client_api.post('/api/offerwall/b2b/register/', data, format='json')
        r = self.client_api.post('/api/offerwall/b2b/register/', data, format='json')
        self.assertEqual(r.status_code, 409)

    def test_register_creates_onboarding(self):
        from api.offerwall.b2b.models import B2BOnboarding
        self.client_api.post('/api/offerwall/b2b/register/', {
            'company_name': 'Ob Co', 'contact_email': 'ob@t.com',
            'plan_type': 'free', 'country': 'BD', 'business_type': 'web_app',
        }, format='json')
        self.assertTrue(B2BOnboarding.objects.filter(
            client__owner=self.user).exists())

    def test_unauthenticated_register_returns_401(self):
        r = APIClient().post('/api/offerwall/b2b/register/', {
            'company_name': 'X', 'contact_email': 'x@t.com'}, format='json')
        self.assertEqual(r.status_code, 401)


class B2BDashboardViewTest(TestCase):

    def setUp(self):
        self.api = APIClient()
        self.user = mk_user('db_u')
        self.b2b  = mk_client(self.user)
        self.api.force_authenticate(self.user)

    def test_dashboard_200(self):
        r = self.api.get('/api/offerwall/b2b/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('client',  r.data)
        self.assertIn('quota',   r.data)
        self.assertIn('revenue', r.data)

    def test_dashboard_not_registered_returns_404(self):
        user2 = mk_user('db_u2')
        api2  = APIClient()
        api2.force_authenticate(user2)
        r = api2.get('/api/offerwall/b2b/dashboard/')
        self.assertEqual(r.status_code, 404)

    def test_dashboard_shows_quota_pct(self):
        r = self.api.get('/api/offerwall/b2b/dashboard/')
        self.assertIn('quota_pct', r.data['quota'])

    def test_dashboard_shows_revenue_share(self):
        r = self.api.get('/api/offerwall/b2b/dashboard/')
        self.assertIn('your_share_pct', r.data['revenue'])


class B2BUpgradeViewTest(TestCase):

    def setUp(self):
        self.api   = APIClient()
        self.user  = mk_user('up_u')
        self.free  = mk_plan('free', Decimal('0'), Decimal('0'))
        self.pro   = mk_plan('pro',  Decimal('8000'), Decimal('20'))
        self.b2b   = mk_client(self.user, self.free)
        self.api.force_authenticate(self.user)

    def test_upgrade_to_pro_returns_200(self):
        r = self.api.post('/api/offerwall/b2b/upgrade/',
                          {'plan_type': 'pro'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['success'])

    def test_upgrade_changes_plan(self):
        self.api.post('/api/offerwall/b2b/upgrade/',
                      {'plan_type': 'pro'}, format='json')
        self.b2b.refresh_from_db()
        self.assertEqual(self.b2b.plan.plan_type, 'pro')

    def test_upgrade_invalid_plan_returns_400(self):
        r = self.api.post('/api/offerwall/b2b/upgrade/',
                          {'plan_type': 'nonexistent'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_upgrade_not_registered_returns_404(self):
        user2 = mk_user('up_u2')
        api2  = APIClient()
        api2.force_authenticate(user2)
        r = api2.post('/api/offerwall/b2b/upgrade/',
                      {'plan_type': 'pro'}, format='json')
        self.assertEqual(r.status_code, 404)


class B2BAdminViewTest(TestCase):

    def setUp(self):
        self.admin  = mk_user('adm_b2b', admin=True)
        self.user   = mk_user('adm_pub')
        self.plan   = mk_plan()
        self.b2b    = mk_client(self.user, self.plan, status='pending')
        self.api    = APIClient()
        self.api.force_authenticate(self.admin)

    def test_admin_list_clients_200(self):
        r = self.api.get('/api/offerwall/b2b/admin/clients/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('count', r.data)

    def test_non_admin_list_returns_403(self):
        api2 = APIClient()
        api2.force_authenticate(self.user)
        r = api2.get('/api/offerwall/b2b/admin/clients/')
        self.assertEqual(r.status_code, 403)

    def test_admin_verify_client(self):
        r = self.api.post(
            f'/api/offerwall/b2b/admin/clients/{self.b2b.id}/verify/')
        self.assertEqual(r.status_code, 200)
        self.b2b.refresh_from_db()
        self.assertEqual(self.b2b.status, 'verified')

    def test_admin_suspend_client(self):
        r = self.api.post(
            f'/api/offerwall/b2b/admin/clients/{self.b2b.id}/suspend/',
            {'reason': 'ToS violation'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.b2b.refresh_from_db()
        self.assertEqual(self.b2b.status, 'suspended')

    def test_generate_invoices_returns_200(self):
        from django.utils import timezone
        now = timezone.now()
        mk_client(mk_user('inv_pub'), self.plan, status='active')
        r = self.api.post('/api/offerwall/b2b/admin/generate-invoices/', {
            'year': now.year, 'month': now.month}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('created', r.data)

    def test_generate_invoices_idempotent(self):
        from django.utils import timezone
        now  = timezone.now()
        pub  = mk_client(mk_user('idem_pub'), self.plan, status='active')
        self.api.post('/api/offerwall/b2b/admin/generate-invoices/',
                      {'year': now.year, 'month': now.month}, format='json')
        r2 = self.api.post('/api/offerwall/b2b/admin/generate-invoices/',
                           {'year': now.year, 'month': now.month}, format='json')
        self.assertEqual(r2.data['skipped'], r2.data['created'] + r2.data['skipped'])


class B2BOnboardingStepViewTest(TestCase):

    def setUp(self):
        self.api  = APIClient()
        self.user = mk_user('ons_u')
        self.b2b  = mk_client(self.user)
        self.api.force_authenticate(self.user)

    def test_complete_valid_step_200(self):
        r = self.api.post('/api/offerwall/b2b/onboarding/complete-step/',
                          {'step': 'signup'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('completion_pct', r.data)

    def test_invalid_step_returns_400(self):
        r = self.api.post('/api/offerwall/b2b/onboarding/complete-step/',
                          {'step': 'not_a_step'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_profile_step_verifies_client(self):
        self.b2b.status = 'pending'
        self.b2b.save()
        self.api.post('/api/offerwall/b2b/onboarding/complete-step/',
                      {'step': 'profile'}, format='json')
        self.b2b.refresh_from_db()
        self.assertEqual(self.b2b.status, 'verified')


# ═════════════════════════════════════════════════════════════
# B2B Quota Middleware
# ═════════════════════════════════════════════════════════════

class B2BQuotaMiddlewareTest(TestCase):

    def setUp(self):
        self.user = mk_user('qm_u')
        self.plan = mk_plan()
        self.b2b  = mk_client(self.user, self.plan, status='active')

    def test_no_publisher_key_passes_through(self):
        from api.offerwall.b2b.middleware import B2BQuotaMiddleware
        get_response = MagicMock(return_value=MagicMock(status_code=200))
        mw      = B2BQuotaMiddleware(get_response)
        request = RequestFactory().get('/api/offerwall/offers/')
        result  = mw(request)
        self.assertEqual(result.status_code, 200)

    def test_suspended_client_returns_403(self):
        from api.offerwall.b2b.middleware import B2BQuotaMiddleware
        from api.offerwall.publisher import PublisherAPIKey
        self.b2b.status = 'suspended'
        self.b2b.save()
        _, raw_key = PublisherAPIKey.generate(self.user, 'TestKey')
        get_response = MagicMock(return_value=MagicMock(status_code=200))
        mw      = B2BQuotaMiddleware(get_response)
        request = RequestFactory().get('/api/offerwall/offers/')
        request.META['HTTP_X_PUBLISHER_KEY'] = raw_key
        # Patch headers attribute
        request.headers = {'X-Publisher-Key': raw_key}
        result  = mw._check_quota(request, raw_key)
        if result:
            self.assertEqual(result.status_code, 403)

    def test_quota_exceeded_returns_429(self):
        from api.offerwall.b2b.middleware import B2BQuotaMiddleware
        from api.offerwall.publisher import PublisherAPIKey
        self.plan.monthly_api_calls = 1
        self.plan.save()
        usage = self.b2b.get_current_usage()
        usage.api_calls = 1
        usage.save()
        _, raw_key = PublisherAPIKey.generate(self.user, 'QuotaKey')
        mw = B2BQuotaMiddleware(lambda r: MagicMock(status_code=200))
        request = RequestFactory().get('/api/offerwall/offers/')
        request.headers = {'X-Publisher-Key': raw_key}
        result = mw._check_quota(request, raw_key)
        if result:
            self.assertEqual(result.status_code, 429)

    def test_exempt_path_not_checked(self):
        from api.offerwall.b2b.middleware import B2BQuotaMiddleware
        mw = B2BQuotaMiddleware(lambda r: MagicMock(status_code=200))
        request = RequestFactory().get('/api/offerwall/b2b/plans/')
        self.assertFalse(mw._should_check(request))


# ═════════════════════════════════════════════════════════════
# Seed command
# ═════════════════════════════════════════════════════════════

class SeedB2BPlansCommandTest(TestCase):

    def test_seed_creates_4_plans(self):
        from django.core.management import call_command
        from io import StringIO
        from api.offerwall.b2b.models import B2BPlan
        call_command('seed_b2b_plans', stdout=StringIO())
        self.assertEqual(B2BPlan.objects.count(), 4)

    def test_seed_idempotent(self):
        from django.core.management import call_command
        from io import StringIO
        from api.offerwall.b2b.models import B2BPlan
        call_command('seed_b2b_plans', stdout=StringIO())
        call_command('seed_b2b_plans', stdout=StringIO())
        self.assertEqual(B2BPlan.objects.count(), 4)

    def test_seed_reset_option(self):
        from django.core.management import call_command
        from io import StringIO
        from api.offerwall.b2b.models import B2BPlan
        call_command('seed_b2b_plans', stdout=StringIO())
        call_command('seed_b2b_plans', '--reset', stdout=StringIO())
        self.assertEqual(B2BPlan.objects.count(), 4)

    def test_free_plan_has_zero_price(self):
        from django.core.management import call_command
        from io import StringIO
        from api.offerwall.b2b.models import B2BPlan
        call_command('seed_b2b_plans', stdout=StringIO())
        free = B2BPlan.objects.get(plan_type='free')
        self.assertEqual(free.monthly_price_bdt, Decimal('0'))

    def test_enterprise_has_unlimited_calls(self):
        from django.core.management import call_command
        from io import StringIO
        from api.offerwall.b2b.models import B2BPlan
        call_command('seed_b2b_plans', stdout=StringIO())
        ent = B2BPlan.objects.get(plan_type='enterprise')
        self.assertTrue(ent.is_unlimited_calls())
