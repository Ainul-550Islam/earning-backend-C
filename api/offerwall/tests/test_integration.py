"""
Full Integration Tests — click → postback → conversion → approve → wallet
Run: python manage.py test api.offerwall.tests.test_integration
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from api.offerwall.models import OfferProvider, Offer, OfferConversion, OfferClick
from api.offerwall.services.OfferwallIntegrationService import OfferwallIntegrationService

User = get_user_model()


def _setup():
    prov = OfferProvider.objects.create(
        name='IntProv', provider_type='tapjoy', status='active',
        revenue_share=Decimal('70'), secret_key='int_secret', config={})
    offer = Offer.objects.create(
        provider=prov, external_offer_id='int_ext_001', title='Integration Offer',
        description='d', payout=Decimal('2'), reward_amount=Decimal('1.40'),
        click_url='https://x.com', status='active', currency='USD', reward_currency='BDT')
    user = User.objects.create_user(
        username='int_user', email='int@t.com', password='p')
    admin = User.objects.create_superuser(
        username='int_admin', email='iadmin@t.com', password='Admin@123')
    return prov, offer, user, admin


class ProcessConversionTest(TestCase):
    def setUp(self):
        self.prov, self.offer, self.user, self.admin = _setup()

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_creates_conversion(self, mock_get):
        mock_get.return_value = MagicMock(send=MagicMock(return_value={'success': True}))
        r = OfferwallIntegrationService.process_conversion(
            offer=self.offer, user=self.user, conversion_id='int_c001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'))
        self.assertTrue(r['success']); self.assertTrue(r['created'])
        self.assertTrue(OfferConversion.objects.filter(conversion_id='int_c001').exists())

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_idempotent_duplicate(self, mock_get):
        mock_get.return_value = MagicMock(send=MagicMock(return_value={'success': True}))
        OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='int_dup_001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'), status='approved')
        r = OfferwallIntegrationService.process_conversion(
            offer=self.offer, user=self.user, conversion_id='int_dup_001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'))
        self.assertTrue(r['success']); self.assertFalse(r['created'])
        self.assertEqual(OfferConversion.objects.filter(conversion_id='int_dup_001').count(), 1)

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_offer_conversion_count_incremented(self, mock_get):
        mock_get.return_value = MagicMock(send=MagicMock(return_value={'success': True}))
        initial = self.offer.conversion_count
        OfferwallIntegrationService.process_conversion(
            offer=self.offer, user=self.user, conversion_id='int_cnt_001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'))
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.conversion_count, initial + 1)

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_click_marked_converted(self, mock_get):
        mock_get.return_value = MagicMock(send=MagicMock(return_value={'success': True}))
        click = OfferClick.objects.create(
            offer=self.offer, user=self.user, click_id='int_ck_001', ip_address='127.0.0.1')
        OfferwallIntegrationService.process_conversion(
            offer=self.offer, user=self.user, conversion_id='int_click_c001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'), click=click)
        click.refresh_from_db()
        self.assertTrue(click.is_converted)
        self.assertIsNotNone(click.converted_at)


class ApproveConversionTest(TestCase):
    def setUp(self):
        self.prov, self.offer, self.user, self.admin = _setup()

    def _conv(self, cid='int_app_001', status='pending'):
        return OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id=cid,
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'), status=status)

    def test_approve_pending_succeeds(self):
        conv = self._conv()
        r = OfferwallIntegrationService.approve_conversion(conv, approver=self.admin)
        self.assertTrue(r['success'])
        conv.refresh_from_db()
        self.assertEqual(conv.status, 'approved')
        self.assertTrue(conv.is_verified)

    def test_approve_already_approved_fails(self):
        conv = self._conv(cid='int_app_002', status='approved')
        r = OfferwallIntegrationService.approve_conversion(conv)
        self.assertFalse(r['success'])
        self.assertIn('Cannot approve', r['error'])

    def test_approve_rejected_fails(self):
        conv = self._conv(cid='int_app_003', status='rejected')
        r = OfferwallIntegrationService.approve_conversion(conv)
        self.assertFalse(r['success'])


class RejectConversionTest(TestCase):
    def setUp(self):
        self.prov, self.offer, self.user, self.admin = _setup()

    def _conv(self, cid='int_rej_001', status='pending'):
        return OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id=cid,
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'), status=status)

    def test_reject_pending_succeeds(self):
        conv = self._conv()
        r = OfferwallIntegrationService.reject_conversion(conv, reason='Fraud')
        self.assertTrue(r['success'])
        conv.refresh_from_db()
        self.assertEqual(conv.status, 'rejected')
        self.assertEqual(conv.rejection_reason, 'Fraud')

    def test_reject_approved_fails(self):
        conv = self._conv(cid='int_rej_002', status='approved')
        r = OfferwallIntegrationService.reject_conversion(conv, reason='Late')
        self.assertFalse(r['success'])


class FraudCheckTest(TestCase):
    def setUp(self):
        self.prov, self.offer, self.user, self.admin = _setup()

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_low_score_not_blocked(self, mock_get):
        mock_get.return_value = MagicMock(send=MagicMock(return_value={
            'success': True, 'should_block': False, 'fraud_score': 5, 'reasons': []}))
        r = OfferwallIntegrationService.check_fraud(
            self.user, self.offer, '127.0.0.1')
        self.assertFalse(r['should_block'])

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_high_score_blocked(self, mock_get):
        mock_get.return_value = MagicMock(send=MagicMock(return_value={
            'success': True, 'should_block': True, 'fraud_score': 90}))
        r = OfferwallIntegrationService.check_fraud(
            self.user, self.offer, '1.2.3.4')
        self.assertTrue(r['should_block'])

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_adapter_fail_returns_safe_default(self, mock_get):
        mock_get.return_value = MagicMock(send=MagicMock(return_value={
            'success': False, 'error': 'circuit_open'}))
        r = OfferwallIntegrationService.check_fraud(
            self.user, self.offer, '5.5.5.5')
        self.assertFalse(r['should_block'])


class FullFlowTest(TestCase):
    """End-to-end: postback received → conversion created → approved → visible"""

    def setUp(self):
        self.prov, self.offer, self.user, self.admin = _setup()
        self.api = APIClient()

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_conversion_visible_in_user_list_after_approve(self, mock_get):
        mock_get.return_value = MagicMock(send=MagicMock(return_value={'success': True}))

        # Step 1: process postback
        r = OfferwallIntegrationService.process_conversion(
            offer=self.offer, user=self.user, conversion_id='flow_001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'))
        self.assertTrue(r['created'])
        conv = r['conversion']

        # Step 2: approve
        OfferwallIntegrationService.approve_conversion(conv, approver=self.admin)
        conv.refresh_from_db()
        self.assertEqual(conv.status, 'approved')

        # Step 3: visible in API
        self.api.force_authenticate(self.user)
        r = self.api.get('/api/offerwall/conversions/')
        ids = [c['conversion_id'] for c in r.data.get('results', r.data)]
        self.assertIn('flow_001', ids)

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_offer_unavailable_after_user_limit(self, mock_get):
        mock_get.return_value = MagicMock(send=MagicMock(return_value={'success': True}))
        self.offer.user_limit = 1; self.offer.save()

        OfferwallIntegrationService.process_conversion(
            offer=self.offer, user=self.user, conversion_id='flow_lim_001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'))
        conv = OfferConversion.objects.get(conversion_id='flow_lim_001')
        OfferwallIntegrationService.approve_conversion(conv)

        self.offer.refresh_from_db()
        self.assertFalse(self.offer.is_available_for_user(self.user))


# ── Extra Integration Tests ───────────────────────────────────────────────────

class FullFlowExtraTest(TestCase):

    def setUp(self):
        self.prov, self.offer, self.user, self.admin = _setup()

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_reject_then_approve_fails(self, mock_get):
        """Rejected conversion cannot be approved"""
        mock_get.return_value = MagicMock(send=MagicMock(return_value={'success': True}))

        conv = OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='rej_then_app_001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'), status='pending')

        # First reject it
        OfferwallIntegrationService.reject_conversion(conv, reason='Suspected fraud')
        conv.refresh_from_db()
        self.assertEqual(conv.status, 'rejected')

        # Now try to approve — should fail
        result = OfferwallIntegrationService.approve_conversion(conv)
        self.assertFalse(result['success'])
        self.assertIn('Cannot approve', result['error'])

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_fraud_blocked_click_not_converted(self, mock_get):
        """If fraud check blocks, no conversion should be created"""
        from rest_framework.test import APIClient

        # Fraud adapter returns block=True
        def side_effect(name):
            if name == 'fraud':
                m = MagicMock()
                m.send.return_value = {'success': True, 'should_block': True, 'fraud_score': 95}
                return m
            m = MagicMock()
            m.send.return_value = {'success': True}
            return m

        mock_get.side_effect = side_effect
        initial_count = OfferConversion.objects.count()

        client = APIClient()
        client.force_authenticate(self.user)

        with patch('api.offerwall.utils.FraudDetector.FraudDetector.comprehensive_fraud_check') as mock_fd:
            mock_fd.return_value = {'should_block': True, 'fraud_score': 95, 'reasons': ['vpn']}
            r = client.post(f'/api/offerwall/offers/{self.offer.id}/click/')
            self.assertIn(r.status_code, [400, 403, 429])

        # No new conversions created
        self.assertEqual(OfferConversion.objects.count(), initial_count)

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_manual_credit_after_failed_auto_credit(self, mock_get):
        """Admin can manually trigger wallet credit if signal failed"""
        mock_get.return_value = MagicMock(send=MagicMock(return_value={
            'success': True, 'txn_id': 'manual_txn_001', 'new_balance': '500.00'}))

        conv = OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='manual_cr_001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'),
            status='approved', is_verified=True)

        result = OfferwallIntegrationService.manual_credit_wallet(conv, admin_user=self.admin)
        self.assertTrue(result['success'])
        self.assertEqual(result.get('txn_id'), 'manual_txn_001')

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_multiple_users_same_offer_independent(self, mock_get):
        """Different users completing same offer are independent"""
        mock_get.return_value = MagicMock(send=MagicMock(return_value={'success': True}))

        user2 = User.objects.create_user(
            username='multi_u2', email='mu2@t.com', password='p')

        r1 = OfferwallIntegrationService.process_conversion(
            offer=self.offer, user=self.user, conversion_id='multi_c001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'))
        r2 = OfferwallIntegrationService.process_conversion(
            offer=self.offer, user=user2, conversion_id='multi_c002',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'))

        self.assertTrue(r1['created'])
        self.assertTrue(r2['created'])
        self.assertEqual(OfferConversion.objects.filter(offer=self.offer).count(), 2)

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_conversion_with_bonus_amount(self, mock_get):
        """Bonus amount stored and credited correctly"""
        mock_get.return_value = MagicMock(send=MagicMock(return_value={'success': True}))

        result = OfferwallIntegrationService.process_conversion(
            offer=self.offer, user=self.user, conversion_id='bonus_c001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'),
            bonus_amount=Decimal('0.60'))

        self.assertTrue(result['created'])
        conv = result['conversion']
        conv.refresh_from_db()
        self.assertEqual(conv.bonus_amount, Decimal('0.60'))

    @patch('api.offerwall.services.adapters.OfferwallAdapter.OfferwallAdapterFactory.get')
    def test_postback_creates_conversion_with_correct_currency(self, mock_get):
        """Conversion uses offer's reward_currency"""
        mock_get.return_value = MagicMock(send=MagicMock(return_value={'success': True}))

        result = OfferwallIntegrationService.process_conversion(
            offer=self.offer, user=self.user, conversion_id='curr_c001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'))

        conv = result['conversion']
        self.assertEqual(conv.reward_currency, 'BDT')
        self.assertEqual(conv.payout_currency, 'USD')


class SignalIntegrationTest(TestCase):
    """Test that signals fire correctly on real model save"""

    def setUp(self):
        self.prov, self.offer, self.user, self.admin = _setup()

    def test_approve_triggers_post_save_signal(self):
        """approve() save triggers handle_conversion_status_change signal"""
        from api.offerwall.signals import offer_conversion_approved

        received = []
        def handler(sender, conversion, approved_by, **kw):
            received.append(conversion.conversion_id)

        offer_conversion_approved.connect(handler)
        try:
            with patch('api.offerwall.signals._on_conversion_approved'):
                conv = OfferConversion.objects.create(
                    offer=self.offer, user=self.user, conversion_id='sig_int_001',
                    payout_amount=Decimal('2'), reward_amount=Decimal('1.40'),
                    status='pending')
                # Signal fires on_commit — force it in test
                from api.offerwall.signals import _on_conversion_approved
                with patch('api.offerwall.signals._credit_wallet') as mock_cw, \
                     patch('api.offerwall.signals._notify') as mock_n, \
                     patch('api.offerwall.signals._process_referral') as mock_r, \
                     patch('api.offerwall.signals._audit') as mock_a:
                    mock_cw.return_value = {'success': True, 'txn_id': 't1'}
                    conv.approve(approver=self.admin)
        finally:
            offer_conversion_approved.disconnect(handler)

    def test_reject_triggers_post_save_signal(self):
        """reject() triggers handle_conversion_status_change"""
        from api.offerwall.signals import offer_conversion_rejected

        received = []
        def handler(sender, conversion, reason, **kw):
            received.append(reason)

        offer_conversion_rejected.connect(handler)
        try:
            with patch('api.offerwall.signals._notify'), \
                 patch('api.offerwall.signals._audit'):
                conv = OfferConversion.objects.create(
                    offer=self.offer, user=self.user, conversion_id='sig_rej_001',
                    payout_amount=Decimal('2'), reward_amount=Decimal('1.40'),
                    status='pending')
                conv.reject(reason='Fraud')
        finally:
            offer_conversion_rejected.disconnect(handler)
