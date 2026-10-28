"""
tests/test_b2b_services.py — B2BClientService + B2BInvoiceService (0 tests before)
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class B2BClientServiceTest(TestCase):

    def setUp(self):
        from api.offerwall.b2b.tests.factories import B2BClientFactory, B2BPlanFactory
        self.client_obj = B2BClientFactory(status='pending')
        self.pro_plan   = B2BPlanFactory(plan_type='pro')

    # ── upgrade_plan ─────────────────────────────────────────

    def test_upgrade_plan_success(self):
        from api.offerwall.b2b.services import B2BClientService
        result = B2BClientService.upgrade_plan(self.client_obj, 'pro')
        self.assertTrue(result['success'])
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.plan.plan_type, 'pro')

    def test_upgrade_plan_invalid_type(self):
        from api.offerwall.b2b.services import B2BClientService
        result = B2BClientService.upgrade_plan(self.client_obj, 'unknown_tier')
        self.assertFalse(result['success'])
        self.assertIn('available', result)

    def test_upgrade_plan_completes_onboarding_step(self):
        from api.offerwall.b2b.services import B2BClientService
        from api.offerwall.b2b.models import B2BOnboarding
        B2BOnboarding.objects.get_or_create(client=self.client_obj)
        B2BClientService.upgrade_plan(self.client_obj, 'pro')
        self.client_obj.onboarding.refresh_from_db()
        self.assertIn('plan', self.client_obj.onboarding.completed_steps)

    # ── verify_client ────────────────────────────────────────

    def test_verify_client(self):
        from api.offerwall.b2b.services import B2BClientService
        result = B2BClientService.verify_client(self.client_obj)
        self.assertTrue(result['success'])
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.status, 'verified')
        self.assertIsNotNone(self.client_obj.verified_at)

    # ── activate_client ──────────────────────────────────────

    def test_activate_client(self):
        from api.offerwall.b2b.services import B2BClientService
        result = B2BClientService.activate_client(self.client_obj)
        self.assertTrue(result['success'])
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.status, 'active')

    # ── suspend_client ───────────────────────────────────────

    def test_suspend_client(self):
        from api.offerwall.b2b.services import B2BClientService
        self.client_obj.status = 'active'
        self.client_obj.save()
        result = B2BClientService.suspend_client(
            self.client_obj, reason='TOS violation')
        self.assertTrue(result['success'])
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.status, 'suspended')
        self.assertIn('TOS', self.client_obj.suspension_reason)

    # ── complete_onboarding_step ─────────────────────────────

    def test_complete_onboarding_step_valid(self):
        from api.offerwall.b2b.services import B2BClientService
        from api.offerwall.b2b.models import B2BOnboarding
        B2BOnboarding.objects.get_or_create(client=self.client_obj)
        result = B2BClientService.complete_onboarding_step(
            self.client_obj, 'profile')
        self.assertTrue(result['success'])
        self.assertGreater(result['completion_pct'], 0)

    def test_complete_onboarding_step_invalid(self):
        from api.offerwall.b2b.services import B2BClientService
        result = B2BClientService.complete_onboarding_step(
            self.client_obj, 'nonexistent_step')
        self.assertFalse(result['success'])
        self.assertIn('valid', result)

    def test_profile_step_auto_verifies_pending(self):
        from api.offerwall.b2b.services import B2BClientService
        from api.offerwall.b2b.models import B2BOnboarding
        B2BOnboarding.objects.get_or_create(client=self.client_obj)
        B2BClientService.complete_onboarding_step(self.client_obj, 'profile')
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.status, 'verified')

    # ── get_dashboard_data ───────────────────────────────────

    def test_get_dashboard_data_structure(self):
        from api.offerwall.b2b.services import B2BClientService
        data = B2BClientService.get_dashboard_data(self.client_obj)
        self.assertIn('quota', data)
        self.assertIn('revenue', data)
        self.assertIn('onboarding', data)
        self.assertIn('api_calls_used', data['quota'])
        self.assertIn('quota_pct', data['quota'])

    def test_get_dashboard_quota_pct_zero_for_new(self):
        from api.offerwall.b2b.services import B2BClientService
        data = B2BClientService.get_dashboard_data(self.client_obj)
        self.assertEqual(data['quota']['api_calls_used'], 0)


class B2BInvoiceServiceTest(TestCase):

    def setUp(self):
        from api.offerwall.b2b.tests.factories import B2BClientFactory
        self.client_obj = B2BClientFactory(status='active')
        from django.utils import timezone
        now = timezone.now()
        self.year  = now.year
        self.month = now.month

    def test_generate_invoice_creates_record(self):
        from api.offerwall.b2b.services import B2BInvoiceService
        from api.offerwall.b2b.models import B2BInvoice
        result = B2BInvoiceService.generate_for_period(
            self.year, self.month)
        self.assertGreaterEqual(result['created'], 1)
        self.assertEqual(B2BInvoice.objects.filter(
            client=self.client_obj,
            period_year=self.year,
            period_month=self.month).count(), 1)

    def test_generate_invoice_idempotent(self):
        from api.offerwall.b2b.services import B2BInvoiceService
        B2BInvoiceService.generate_for_period(self.year, self.month)
        result = B2BInvoiceService.generate_for_period(self.year, self.month)
        self.assertEqual(result['created'], 0)
        self.assertGreaterEqual(result['skipped'], 1)

    def test_invoice_number_unique_format(self):
        from api.offerwall.b2b.services import B2BInvoiceService
        from api.offerwall.b2b.models import B2BInvoice
        B2BInvoiceService.generate_for_period(self.year, self.month)
        inv = B2BInvoice.objects.filter(
            client=self.client_obj).first()
        self.assertTrue(inv.invoice_number.startswith('INV-'))

    def test_invoice_totals_calculated_correctly(self):
        from api.offerwall.b2b.services import B2BInvoiceService
        from api.offerwall.b2b.models import B2BInvoice
        B2BInvoiceService.generate_for_period(self.year, self.month)
        inv = B2BInvoice.objects.filter(client=self.client_obj).first()
        # total_due = plan_fee + tax
        expected = inv.plan_fee_bdt + inv.tax_bdt
        self.assertAlmostEqual(
            float(inv.total_due_bdt), float(expected), places=2)

    def test_generate_handles_no_active_clients(self):
        from api.offerwall.b2b.services import B2BInvoiceService
        from api.offerwall.b2b.models import B2BClient
        B2BClient.objects.all().update(status='churned')
        result = B2BInvoiceService.generate_for_period(self.year, self.month)
        self.assertEqual(result['created'], 0)
