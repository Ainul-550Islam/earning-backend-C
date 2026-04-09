# api/djoyalty/tests/test_serializers.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_txn, make_event, make_loyalty_points


class CustomerSerializerTest(TestCase):

    def setUp(self):
        self.customer = make_customer(
            code='SRLCUST01', firstname='Serial', lastname='Test',
            email='serial@example.com', newsletter=True,
        )

    def test_serializer_full_name(self):
        from djoyalty.serializers.CustomerSerializer import CustomerSerializer
        s = CustomerSerializer(self.customer)
        self.assertEqual(s.data['full_name'], 'Serial Test')

    def test_serializer_code_uppercase(self):
        from djoyalty.serializers.CustomerSerializer import CustomerSerializer
        s = CustomerSerializer(data={'code': 'newcode01', 'email': 'x@x.com'})
        s.is_valid()
        self.assertEqual(s.validated_data.get('code', ''), 'NEWCODE01')

    def test_serializer_invalid_email(self):
        from djoyalty.serializers.CustomerSerializer import CustomerSerializer
        s = CustomerSerializer(data={'code': 'CUST99', 'email': 'not-an-email'})
        self.assertFalse(s.is_valid())
        self.assertIn('email', s.errors)

    def test_serializer_points_balance(self):
        from djoyalty.serializers.CustomerSerializer import CustomerSerializer
        make_loyalty_points(self.customer, balance=Decimal('250'))
        s = CustomerSerializer(self.customer)
        self.assertEqual(s.data['points_balance'], '250')


class TxnSerializerTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='SRLCUST02')
        self.txn = make_txn(self.customer, value=Decimal('100'), is_discount=False)

    def test_type_label_full_price(self):
        from djoyalty.serializers.TxnSerializer import TxnSerializer
        s = TxnSerializer(self.txn)
        self.assertEqual(s.data['type_label'], 'Full Price')

    def test_type_label_discount(self):
        from djoyalty.serializers.TxnSerializer import TxnSerializer
        discount_txn = make_txn(self.customer, value=Decimal('50'), is_discount=True)
        s = TxnSerializer(discount_txn)
        self.assertEqual(s.data['type_label'], 'Discount')

    def test_customer_name_field(self):
        from djoyalty.serializers.TxnSerializer import TxnSerializer
        s = TxnSerializer(self.txn)
        self.assertIn('SRLCUST02', s.data['customer_name'])


class EventSerializerTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='SRLCUST03')

    def test_anonymous_event(self):
        from djoyalty.serializers.EventSerializer import EventSerializer
        evt = make_event(customer=None, action='page_view')
        s = EventSerializer(evt)
        self.assertTrue(s.data['is_anonymous'])
        self.assertEqual(s.data['customer_name'], 'Anonymous')

    def test_customer_event(self):
        from djoyalty.serializers.EventSerializer import EventSerializer
        evt = make_event(self.customer, action='login')
        s = EventSerializer(evt)
        self.assertFalse(s.data['is_anonymous'])

    def test_empty_action_invalid(self):
        from djoyalty.serializers.EventSerializer import EventSerializer
        s = EventSerializer(data={'action': '', 'customer': None})
        s.is_valid()
        self.assertIn('action', s.errors)
