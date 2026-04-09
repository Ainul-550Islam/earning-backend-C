# api/djoyalty/tests/test_models.py
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from .factories import make_customer, make_txn, make_event, make_loyalty_points, make_tier


class CustomerModelTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='TESTCUST01', firstname='John', lastname='Doe', email='john@example.com')

    def test_customer_str(self):
        self.assertIn('TESTCUST01', str(self.customer))

    def test_customer_full_name(self):
        self.assertEqual(self.customer.full_name, 'John Doe')

    def test_customer_full_name_unnamed(self):
        c = make_customer(code='NONAME01', firstname=None, lastname=None)
        self.assertEqual(c.full_name, 'Unnamed')

    def test_customer_points_balance_default(self):
        self.assertEqual(self.customer.points_balance, 0)

    def test_customer_points_balance_with_points(self):
        make_loyalty_points(self.customer, balance=Decimal('250'))
        self.assertEqual(self.customer.points_balance, Decimal('250'))

    def test_customer_current_tier_none(self):
        self.assertIsNone(self.customer.current_tier)

    def test_customer_is_active_default(self):
        self.assertTrue(self.customer.is_active)

    def test_customer_newsletter_default(self):
        self.assertTrue(self.customer.newsletter)


class TxnModelTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='TXNCUST01')
        self.txn = make_txn(self.customer, value=Decimal('100'))

    def test_txn_str(self):
        result = str(self.txn)
        self.assertIn('100', result)

    def test_txn_is_discount_default(self):
        self.assertFalse(self.txn.is_discount)

    def test_txn_discount_flag(self):
        discount_txn = make_txn(self.customer, value=Decimal('50'), is_discount=True)
        self.assertTrue(discount_txn.is_discount)

    def test_txn_customer_link(self):
        self.assertEqual(self.txn.customer, self.customer)

    def test_txn_full_price_manager(self):
        from djoyalty.models.core import Txn
        make_txn(self.customer, value=Decimal('20'), is_discount=True)
        full_price = Txn.txn_full.filter(customer=self.customer)
        self.assertEqual(full_price.count(), 1)
        self.assertEqual(full_price.first().value, Decimal('100'))

    def test_txn_discount_manager(self):
        from djoyalty.models.core import Txn
        make_txn(self.customer, value=Decimal('30'), is_discount=True)
        discounted = Txn.txn_discount.filter(customer=self.customer)
        self.assertEqual(discounted.count(), 1)


class EventModelTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='EVTCUST01')

    def test_event_with_customer(self):
        evt = make_event(self.customer, action='login')
        self.assertEqual(evt.customer, self.customer)
        self.assertEqual(evt.action, 'login')
        self.assertFalse(evt.customer is None)

    def test_anonymous_event(self):
        evt = make_event(customer=None, action='page_view')
        self.assertIsNone(evt.customer)
        self.assertEqual(evt.action, 'page_view')

    def test_event_str(self):
        evt = make_event(self.customer, action='purchase')
        self.assertIn('purchase', str(evt))

    def test_customer_related_manager(self):
        from djoyalty.models.core import Event
        make_event(self.customer, action='login')
        make_event(customer=None, action='anon_view')
        customer_events = Event.customer_related.filter(customer=self.customer)
        self.assertEqual(customer_events.count(), 1)

    def test_anonymous_manager(self):
        from djoyalty.models.core import Event
        make_event(customer=None, action='anon_action')
        anon_events = Event.anonymous.all()
        self.assertGreaterEqual(anon_events.count(), 1)


class LoyaltyPointsModelTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='PTSCUST01')
        self.lp = make_loyalty_points(self.customer, balance=Decimal('500'))

    def test_points_balance(self):
        self.assertEqual(self.lp.balance, Decimal('500'))

    def test_points_credit(self):
        self.lp.credit(Decimal('100'))
        self.lp.refresh_from_db()
        self.assertEqual(self.lp.balance, Decimal('600'))
        self.assertEqual(self.lp.lifetime_earned, Decimal('100'))

    def test_points_debit(self):
        self.lp.debit(Decimal('200'))
        self.lp.refresh_from_db()
        self.assertEqual(self.lp.balance, Decimal('300'))

    def test_points_debit_insufficient(self):
        from djoyalty.exceptions import InsufficientPointsError
        with self.assertRaises(InsufficientPointsError):
            self.lp.debit(Decimal('10000'))

    def test_points_str(self):
        result = str(self.lp)
        self.assertIn('500', result)
