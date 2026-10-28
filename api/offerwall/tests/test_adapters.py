"""
Adapter Tests — HIGH PRIORITY
Run: python manage.py test api.offerwall.tests.test_adapters
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
User = get_user_model()

def mk_user(un='au'): return User.objects.create_user(username=un, email=f'{un}@t.com', password='p')
def F():
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
    return OfferwallAdapterFactory

class FactoryTest(TestCase):
    def test_all_adapters(self):
        for n in ['wallet','notification','fraud','audit','referral']: F().get(n)
    def test_names(self):
        exp = {'wallet':'wallet','notification':'notification','fraud':'fraud_detection','audit':'audit','referral':'referral'}
        for k,v in exp.items(): self.assertEqual(F().get(k).name, v)
    def test_unknown_raises(self):
        with self.assertRaises(ValueError): F().get('xyz')
    def test_singleton(self): self.assertIs(F().get('wallet'), F().get('wallet'))
    def test_custom_adapter(self):
        from api.offerwall.services.adapters.OfferwallAdapter import BaseOfferwallAdapter, OfferwallAdapterFactory
        class Echo(BaseOfferwallAdapter):
            name = 'echo'
            def _do_send(self, p, **kw): return {'success': True, 'echo': p}
        OfferwallAdapterFactory.register('echo', Echo)
        r = OfferwallAdapterFactory.get('echo').send({'k': 1})
        self.assertTrue(r['success']); self.assertEqual(r['echo']['k'], 1)
    def test_health_check(self):
        h = F().health_check_all()
        for n in ['wallet','notification','fraud','audit','referral']:
            self.assertIn(n, h); self.assertFalse(h[n]['circuit_open'])

class CircuitBreakerTest(TestCase):
    def _fail(self, retries=2):
        from api.offerwall.services.adapters.OfferwallAdapter import BaseOfferwallAdapter
        class Fail(BaseOfferwallAdapter):
            name='fail'; retry_delay=0
            def _do_send(self, p, **kw): raise Exception('down')
        a = Fail(); a.max_retries = retries; return a
    def test_returns_error_dict(self): r = self._fail().send({}); self.assertFalse(r['success'])
    def test_circuit_opens(self): a = self._fail(2); a.send({}); self.assertTrue(a._circuit_open)
    def test_circuit_blocks(self): a = self._fail(); a.send({}); a._last_failure=None; r=a.send({}); self.assertEqual(r.get('error'),'circuit_open')
    def test_success_resets(self):
        from api.offerwall.services.adapters.OfferwallAdapter import BaseOfferwallAdapter
        class OK(BaseOfferwallAdapter):
            name='ok'
            def _do_send(self, p, **kw): return {'success':True}
        a = OK(); a._failure_count = 5; a.send({}); self.assertEqual(a._failure_count, 0)

class WalletAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('wu')
    def _a(self):
        from api.offerwall.services.adapters.OfferwallAdapter import WalletAdapter
        return WalletAdapter()
    def test_zero_amount_error(self):
        r = self._a().send({'user_id': self.user.id, 'reward_amount': '0', 'conversion_id': 'x'})
        self.assertFalse(r['success']); self.assertEqual(r['error'], 'invalid_amount')
    def test_unknown_user_error(self):
        r = self._a().send({'user_id': 99999, 'reward_amount': '1', 'conversion_id': 'x'})
        self.assertFalse(r['success']); self.assertEqual(r['error'], 'user_not_found')
    @patch('api.wallet.services.WalletService.add_earnings')
    @patch('api.wallet.models.Wallet.objects.get_or_create')
    def test_reward_plus_bonus(self, mock_gwc, mock_earn):
        mock_w = MagicMock(); mock_w.current_balance = Decimal('0')
        mock_gwc.return_value = (mock_w, False)
        mock_earn.return_value = MagicMock(txn_id='t1')
        self._a().send({'user_id': self.user.id, 'reward_amount': '0.70', 'bonus_amount': '0.30', 'conversion_id': 'c1'})
        self.assertEqual(mock_earn.call_args.kwargs['amount'], Decimal('1.00'))
    @patch('api.wallet.services.WalletService.add_earnings')
    @patch('api.wallet.models.Wallet.objects.get_or_create')
    def test_exact_params(self, mock_gwc, mock_earn):
        mock_w = MagicMock(); mock_w.current_balance = Decimal('500')
        mock_gwc.return_value = (mock_w, False)
        mock_earn.return_value = MagicMock(txn_id='t2')
        self._a().send({'user_id': self.user.id, 'reward_amount': '1', 'conversion_id': 'cv1',
                        'offer_title': 'T', 'offer_id': 'oid', 'provider_type': 'tapjoy'})
        kw = mock_earn.call_args.kwargs
        self.assertEqual(kw['reference_id'], 'cv1')
        self.assertEqual(kw['source_type'],  'offer')
        self.assertEqual(kw['source_id'],    'cv1')
        self.assertIn('tapjoy', kw['metadata']['provider'])
    @patch('api.wallet.services.WalletService.add_earnings')
    @patch('api.wallet.models.Wallet.objects.get_or_create')
    def test_success_returns_txn(self, mock_gwc, mock_earn):
        mock_w = MagicMock(); mock_w.current_balance = Decimal('1700')
        mock_gwc.return_value = (mock_w, False)
        mock_earn.return_value = MagicMock(txn_id='ok_txn')
        r = self._a().send({'user_id': self.user.id, 'reward_amount': '0.70', 'conversion_id': 'cok'})
        self.assertTrue(r['success']); self.assertEqual(r['txn_id'], 'ok_txn')

class NotificationAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('nu')
    def _a(self):
        from api.offerwall.services.adapters.OfferwallAdapter import NotificationAdapter
        return NotificationAdapter()
    @patch('api.notifications.services.NotificationService.create_notification')
    def test_reward_earned(self, mock_n):
        mock_n.return_value = MagicMock(id='n1')
        self._a().send({'user_id': self.user.id, 'event': 'reward_earned',
                        'offer_title': 'T', 'reward_amount': '0.70', 'reward_currency': 'BDT', 'conversion_id': 'c1'})
        kw = mock_n.call_args.kwargs
        self.assertEqual(kw['notification_type'], 'reward'); self.assertEqual(kw['priority'], 'high')
    @patch('api.notifications.services.NotificationService.create_notification')
    def test_reward_rejected(self, mock_n):
        mock_n.return_value = MagicMock(id='n2')
        self._a().send({'user_id': self.user.id, 'event': 'reward_rejected',
                        'offer_title': 'T', 'reason': 'VPN', 'conversion_id': 'c2'})
        self.assertEqual(mock_n.call_args.kwargs['notification_type'], 'warning')
    @patch('api.notifications.services.NotificationService.create_notification')
    def test_unknown_user(self, mock_n):
        r = self._a().send({'user_id': 99999, 'event': 'reward_earned', 'offer_title': 'X'})
        self.assertFalse(r['success']); mock_n.assert_not_called()

class FraudAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('fu')
    def _a(self):
        from api.offerwall.services.adapters.OfferwallAdapter import FraudAdapter
        return FraudAdapter()
    @patch('api.fraud_detection.services.FraudScoreCalculator.FraudScoreCalculator')
    def test_low_score_not_blocked(self, MC):
        MC.return_value.calculate_overall_risk.return_value = 20
        r = self._a().send({'user_id': self.user.id})
        self.assertFalse(r['should_block']); self.assertEqual(r['risk_level'], 'low')
    @patch('api.fraud_detection.services.FraudScoreCalculator.FraudScoreCalculator')
    def test_75_blocked(self, MC):
        MC.return_value.calculate_overall_risk.return_value = 75
        self.assertTrue(self._a().send({'user_id': self.user.id})['should_block'])
    @patch('api.fraud_detection.services.FraudScoreCalculator.FraudScoreCalculator')
    def test_74_not_blocked(self, MC):
        MC.return_value.calculate_overall_risk.return_value = 74
        self.assertFalse(self._a().send({'user_id': self.user.id})['should_block'])
    @patch('api.fraud_detection.services.FraudScoreCalculator.FraudScoreCalculator')
    def test_called_with_user(self, MC):
        MC.return_value.calculate_overall_risk.return_value = 10
        self._a().send({'user_id': self.user.id}); MC.assert_called_once_with(self.user)
    def test_unknown_user_not_blocked(self):
        r = self._a().send({'user_id': 99999}); self.assertFalse(r['should_block'])
    def test_risk_levels(self):
        from api.offerwall.services.adapters.OfferwallAdapter import FraudAdapter
        a = FraudAdapter()
        for s,l in [(10,'low'),(40,'medium'),(60,'high'),(80,'critical')]:
            self.assertEqual(a._level(s), l)

class AuditAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('adu')
    def _a(self):
        from api.offerwall.services.adapters.OfferwallAdapter import AuditAdapter
        return AuditAdapter()
    @patch('api.audit_logs.services.AuditLogService.log_action')
    def test_offer_complete_mapped(self, mock_log):
        mock_log.return_value = MagicMock(id='l1')
        self._a().send({'user_id': self.user.id, 'action': 'offer_complete', 'message': 'm'})
        self.assertEqual(mock_log.call_args.kwargs['action'], 'OFFER_COMPLETE')
    @patch('api.audit_logs.services.AuditLogService.log_action')
    def test_offer_reject_mapped(self, mock_log):
        mock_log.return_value = MagicMock(id='l2')
        self._a().send({'user_id': self.user.id, 'action': 'offer_reject', 'message': 'm'})
        self.assertEqual(mock_log.call_args.kwargs['action'], 'OFFER_REJECT')
    @patch('api.audit_logs.services.AuditLogService.log_action')
    def test_metadata_passed(self, mock_log):
        mock_log.return_value = MagicMock(id='l3')
        meta = {'k': 'v'}
        self._a().send({'user_id': self.user.id, 'action': 'OFFER_COMPLETE', 'message': 't', 'metadata': meta})
        self.assertEqual(mock_log.call_args.kwargs['metadata'], meta)

class ReferralAdapterTest(TestCase):
    def setUp(self): self.user = mk_user('ru')
    def _a(self):
        from api.offerwall.services.adapters.OfferwallAdapter import ReferralAdapter
        return ReferralAdapter()
    @patch('api.referral.services.ReferralService.process_multilevel_commission')
    def test_correct_params(self, mock_ref):
        mock_ref.return_value = [{'l': 1}]
        r = self._a().send({'user_id': self.user.id, 'earned_amount': '0.70', 'conversion_id': 'cr1'})
        kw = mock_ref.call_args.kwargs
        self.assertEqual(kw['earner'], self.user)
        self.assertEqual(kw['earned_amount'], Decimal('0.70'))
        self.assertEqual(kw['source_type'], 'offer')
        self.assertEqual(kw['source_id'], 'cr1')
    @patch('api.referral.services.ReferralService.process_multilevel_commission')
    def test_commission_count(self, mock_ref):
        mock_ref.return_value = [1, 2]
        r = self._a().send({'user_id': self.user.id, 'earned_amount': '0.70', 'conversion_id': 'cr2'})
        self.assertEqual(r['commissions_paid'], 2)
    def test_zero_amount_skipped(self):
        r = self._a().send({'user_id': self.user.id, 'earned_amount': '0', 'conversion_id': 'cr3'})
        self.assertEqual(r.get('skipped'), 'zero_amount')
    def test_unknown_user_error(self):
        r = self._a().send({'user_id': 99999, 'earned_amount': '1', 'conversion_id': 'x'})
        self.assertFalse(r['success'])
