"""
Signal Tests — HIGH PRIORITY
Run: python manage.py test api.offerwall.tests.test_signals
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from api.offerwall.models import OfferProvider, Offer, OfferConversion
User = get_user_model()

def _setup():
    p = OfferProvider.objects.create(name='SP', provider_type='tapjoy', status='active', revenue_share=Decimal('70'))
    o = Offer.objects.create(provider=p, external_offer_id='s01', title='SO', description='d',
        payout=Decimal('1'), reward_amount=Decimal('0.70'), click_url='https://x.com',
        status='active', currency='USD', reward_currency='BDT')
    u = User.objects.create_user(username='su', email='su@t.com', password='p')
    return p, o, u

def _conv(offer, user, cid='sc1', bonus=Decimal('0')):
    return OfferConversion.objects.create(offer=offer, user=user, conversion_id=cid,
        payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), bonus_amount=bonus, status='pending')


class WalletCreditSignalTest(TestCase):
    def setUp(self): self.prov, self.offer, self.user = _setup()

    @patch('api.wallet.services.WalletService.add_earnings')
    @patch('api.wallet.models.Wallet.objects.get_or_create')
    def test_add_earnings_correct_params(self, mock_gwc, mock_earn):
        mock_w = MagicMock(); mock_w.current_balance = Decimal('0')
        mock_gwc.return_value = (mock_w, True)
        mock_earn.return_value = MagicMock(txn_id='t1')
        conv = _conv(self.offer, self.user)
        from api.offerwall.signals import _credit_wallet
        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
        _credit_wallet(conv, OfferwallAdapterFactory)
        kw = mock_earn.call_args.kwargs
        self.assertEqual(kw['reference_id'], conv.conversion_id)
        self.assertEqual(kw['source_type'], 'offer')
        self.assertIn('offerwall', kw['metadata']['source'])

    @patch('api.wallet.services.WalletService.add_earnings')
    @patch('api.wallet.models.Wallet.objects.get_or_create')
    def test_reward_plus_bonus(self, mock_gwc, mock_earn):
        mock_w = MagicMock(); mock_w.current_balance = Decimal('0')
        mock_gwc.return_value = (mock_w, True)
        mock_earn.return_value = MagicMock(txn_id='t2')
        conv = _conv(self.offer, self.user, cid='sc2', bonus=Decimal('0.30'))
        from api.offerwall.signals import _credit_wallet
        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
        _credit_wallet(conv, OfferwallAdapterFactory)
        self.assertEqual(mock_earn.call_args.kwargs['amount'], Decimal('1.00'))

    @patch('api.wallet.services.WalletService.add_earnings')
    @patch('api.wallet.models.Wallet.objects.get_or_create')
    def test_failure_returns_error_not_raise(self, mock_gwc, mock_earn):
        mock_w = MagicMock(); mock_gwc.return_value = (mock_w, True)
        mock_earn.side_effect = Exception('DB gone')
        conv = _conv(self.offer, self.user, cid='fail1')
        from api.offerwall.signals import _credit_wallet
        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
        r = _credit_wallet(conv, OfferwallAdapterFactory)
        self.assertFalse(r.get('success'))


class NotifySignalTest(TestCase):
    def setUp(self): self.prov, self.offer, self.user = _setup()

    @patch('api.notifications.services.NotificationService.create_notification')
    def test_reward_earned_type(self, mock_n):
        mock_n.return_value = MagicMock(id='n1')
        from api.offerwall.signals import _notify
        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
        _notify(OfferwallAdapterFactory, user_id=self.user.id, event='reward_earned',
                offer_title='T', reward_amount='0.70', reward_currency='BDT', conversion_id='c1')
        self.assertEqual(mock_n.call_args.kwargs['notification_type'], 'reward')
        self.assertEqual(mock_n.call_args.kwargs['priority'], 'high')

    @patch('api.notifications.services.NotificationService.create_notification')
    def test_rejected_warning_type(self, mock_n):
        mock_n.return_value = MagicMock(id='n2')
        from api.offerwall.signals import _notify
        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
        _notify(OfferwallAdapterFactory, user_id=self.user.id, event='reward_rejected',
                offer_title='T', reason='F', conversion_id='c2')
        self.assertEqual(mock_n.call_args.kwargs['notification_type'], 'warning')

    @patch('api.notifications.services.NotificationService.create_notification')
    def test_failure_silently_passes(self, mock_n):
        mock_n.side_effect = Exception('push down')
        from api.offerwall.signals import _notify
        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
        _notify(OfferwallAdapterFactory, user_id=self.user.id, event='reward_earned',
                offer_title='T', conversion_id='c3')


class ReferralSignalTest(TestCase):
    def setUp(self): self.prov, self.offer, self.user = _setup()

    @patch('api.referral.services.ReferralService.process_multilevel_commission')
    def test_commission_correct_params(self, mock_ref):
        mock_ref.return_value = [1]
        conv = _conv(self.offer, self.user, cid='rc1')
        from api.offerwall.signals import _process_referral
        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
        _process_referral(conv, OfferwallAdapterFactory)
        kw = mock_ref.call_args.kwargs
        self.assertEqual(kw['earner'], self.user)
        self.assertEqual(kw['source_type'], 'offer')

    @patch('api.referral.services.ReferralService.process_multilevel_commission')
    def test_failure_silently_passes(self, mock_ref):
        mock_ref.side_effect = Exception('DB down')
        conv = _conv(self.offer, self.user, cid='rf1')
        from api.offerwall.signals import _process_referral
        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
        _process_referral(conv, OfferwallAdapterFactory)


class AuditSignalTest(TestCase):
    def setUp(self): self.prov, self.offer, self.user = _setup()

    @patch('api.audit_logs.services.AuditLogService.log_action')
    def test_audit_called(self, mock_log):
        mock_log.return_value = MagicMock(id='l1')
        from api.offerwall.signals import _audit
        _audit(self.user.id, 'OFFER_COMPLETE', 'ok', {'k': 'v'})
        self.assertEqual(mock_log.call_args.kwargs['action'], 'OFFER_COMPLETE')

    @patch('api.audit_logs.services.AuditLogService.log_action')
    def test_failure_silently_passes(self, mock_log):
        mock_log.side_effect = Exception('gone')
        from api.offerwall.signals import _audit
        _audit(self.user.id, 'OFFER_COMPLETE', 'ok')


class FullApprovalFlowTest(TestCase):
    def setUp(self): self.prov, self.offer, self.user = _setup()

    @patch('api.wallet.services.WalletService.add_earnings')
    @patch('api.wallet.models.Wallet.objects.get_or_create')
    @patch('api.notifications.services.NotificationService.create_notification')
    @patch('api.audit_logs.services.AuditLogService.log_action')
    @patch('api.referral.services.ReferralService.process_multilevel_commission')
    def test_all_systems_called_on_approve(self, mock_ref, mock_audit, mock_notif, mock_gwc, mock_earn):
        mock_w = MagicMock(); mock_w.current_balance = Decimal('0')
        mock_gwc.return_value = (mock_w, True)
        mock_earn.return_value = MagicMock(txn_id='t_all')
        mock_notif.return_value = MagicMock(id='n_all')
        mock_audit.return_value = MagicMock(id='l_all')
        mock_ref.return_value = []
        conv = _conv(self.offer, self.user, cid='all1')
        from api.offerwall.signals import _on_conversion_approved
        _on_conversion_approved(conv)
        mock_earn.assert_called_once()
        mock_notif.assert_called_once()
        mock_ref.assert_called_once()
        mock_audit.assert_called()

    @patch('api.notifications.services.NotificationService.create_notification')
    @patch('api.audit_logs.services.AuditLogService.log_action')
    def test_notify_and_audit_on_reject(self, mock_audit, mock_notif):
        mock_notif.return_value = MagicMock(id='n_rej')
        mock_audit.return_value = MagicMock(id='l_rej')
        conv = _conv(self.offer, self.user, cid='rej1')
        from api.offerwall.signals import _on_conversion_rejected
        _on_conversion_rejected(conv)
        mock_notif.assert_called()   # called at least once
        mock_audit.assert_called()   # called at least once

    @patch('api.wallet.services.WalletService.add_earnings')
    @patch('api.wallet.models.Wallet.objects.get_or_create')
    @patch('api.notifications.services.NotificationService.create_notification')
    @patch('api.audit_logs.services.AuditLogService.log_action')
    @patch('api.referral.services.ReferralService.process_multilevel_commission')
    def test_custom_signal_fires(self, mock_ref, mock_audit, mock_notif, mock_gwc, mock_earn):
        from api.offerwall.signals import offer_conversion_approved
        mock_w = MagicMock(); mock_w.current_balance = Decimal('0')
        mock_gwc.return_value = (mock_w, True)
        mock_earn.return_value = MagicMock(txn_id='t_sig')
        mock_notif.return_value = MagicMock(id='n_sig')
        mock_audit.return_value = MagicMock(id='l_sig')
        mock_ref.return_value = []
        received = []
        def handler(sender, conversion, approved_by, **kw): received.append(conversion.conversion_id)
        offer_conversion_approved.connect(handler)
        try:
            conv = _conv(self.offer, self.user, cid='sig1')
            from api.offerwall.signals import _on_conversion_approved
            _on_conversion_approved(conv)
            self.assertIn('sig1', received)
        finally:
            offer_conversion_approved.disconnect(handler)


# ══════════════════════════════════════════════════════════════════════════════
# CHARGEBACK SIGNAL TESTS
# ══════════════════════════════════════════════════════════════════════════════

import uuid as _uuid
from decimal import Decimal as _D
from unittest.mock import patch as _patch, MagicMock as _MM


def _mk_all(label='sg'):
    from django.contrib.auth import get_user_model
    from api.offerwall.models import OfferProvider, Offer, OfferConversion
    user = get_user_model().objects.create_user(
        username=f'sig_{label}', email=f'sig_{label}@t.com', password='p')
    prov = OfferProvider.objects.create(
        name=f'SP{label}', provider_type='tapjoy', status='active',
        revenue_share=_D('70'))
    offer = Offer.objects.create(
        provider=prov, external_offer_id=_uuid.uuid4().hex[:10],
        title='ST', description='d', payout=_D('1'),
        reward_amount=_D('0.70'), click_url='https://x.com', status='active')
    conv = OfferConversion.objects.create(
        offer=offer, user=user, conversion_id=_uuid.uuid4().hex[:10],
        payout_amount=_D('1'), reward_amount=_D('0.70'),
        bonus_amount=_D('0'), status='approved')
    return user, prov, offer, conv


class ChargebackSignalTest(TestCase):
    def test_chargeback_status_triggers_notify(self):
        user, prov, offer, conv = _mk_all('cb1')
        with _patch('api.offerwall.signals._notify') as mock_notify, \
             _patch('api.offerwall.signals._audit'):
            conv.status = 'chargeback'
            conv.rejection_reason = 'fraud'
            conv.save(update_fields=['status', 'rejection_reason'])
            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args.kwargs
            self.assertEqual(call_kwargs.get('event'), 'reward_rejected')

    def test_chargeback_status_triggers_audit(self):
        user, prov, offer, conv = _mk_all('cb2')
        with _patch('api.offerwall.signals._notify'), \
             _patch('api.offerwall.signals._audit') as mock_audit:
            conv.status = 'chargeback'
            conv.save(update_fields=['status'])
            mock_audit.assert_called_once()
            args = mock_audit.call_args.args
            self.assertEqual(args[1], 'OFFER_CHARGEBACK')

    def test_chargeback_signal_fires(self):
        from api.offerwall.signals import offer_conversion_chargeback
        user, prov, offer, conv = _mk_all('cb3')
        received = []
        def handler(sender, conversion, **kwargs):
            received.append(conversion)
        offer_conversion_chargeback.connect(handler)
        try:
            with _patch('api.offerwall.signals._notify'), \
                 _patch('api.offerwall.signals._audit'):
                conv.status = 'chargeback'
                conv.save(update_fields=['status'])
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0].pk, conv.pk)
        finally:
            offer_conversion_chargeback.disconnect(handler)
