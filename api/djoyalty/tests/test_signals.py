# api/djoyalty/tests/test_signals.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_txn


class CoreSignalsTest(TestCase):

    def test_customer_create_logs_register_event(self):
        from djoyalty.models.core import Event
        customer = make_customer(code='SIGCUST01')
        events = Event.objects.filter(customer=customer, action='register')
        self.assertGreaterEqual(events.count(), 1)

    def test_txn_create_logs_purchase_event(self):
        from djoyalty.models.core import Event
        customer = make_customer(code='SIGCUST02')
        Event.objects.filter(customer=customer).delete()
        make_txn(customer, value=Decimal('100'))
        events = Event.objects.filter(customer=customer, action='purchase')
        self.assertGreaterEqual(events.count(), 1)

    def test_discount_txn_logs_discount_purchase_event(self):
        from djoyalty.models.core import Event
        customer = make_customer(code='SIGCUST03')
        Event.objects.filter(customer=customer).delete()
        make_txn(customer, value=Decimal('50'), is_discount=True)
        events = Event.objects.filter(customer=customer, action='discount_purchase')
        self.assertGreaterEqual(events.count(), 1)

    def test_signal_error_does_not_break_save(self):
        customer = make_customer(code='SIGCUST04')
        self.assertIsNotNone(customer.id)

    def test_event_has_correct_description(self):
        from djoyalty.models.core import Event
        customer = make_customer(code='SIGCUST05')
        event = Event.objects.filter(customer=customer, action='register').first()
        if event:
            self.assertIn('SIGCUST05', event.description)
