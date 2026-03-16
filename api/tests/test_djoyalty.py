from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]

class DjoyaltyTest(TestCase):

    def test_customer_creation(self):
        from api.djoyalty.models import Customer
        try:
            customer = Customer.objects.create(
                code=f'CUST_{uid()}',
                firstname='Test',
                lastname='User',
                email=f'{uid()}@test.com',
            )
            self.assertIsNotNone(customer)
        except Exception as e:
            self.fail(f"Customer creation failed: {e}")

    def test_transaction_creation(self):
        from api.djoyalty.models import Customer, Txn
        try:
            customer = Customer.objects.create(
                code=f'CUST_{uid()}',
            )
            txn = Txn.objects.create(
                customer=customer,
                value=100.00,
                is_discount=False,
            )
            self.assertEqual(txn.value, 100.00)
        except Exception as e:
            self.fail(f"Txn creation failed: {e}")

    def test_discount_transaction(self):
        from api.djoyalty.models import Customer, Txn
        try:
            customer = Customer.objects.create(code=f'CUST_{uid()}')
            txn = Txn.objects.create(
                customer=customer,
                value=80.00,
                is_discount=True,
            )
            self.assertTrue(txn.is_discount)
        except Exception as e:
            self.fail(f"Txn discount failed: {e}")

    def test_event_creation(self):
        from api.djoyalty.models import Customer, Event
        try:
            customer = Customer.objects.create(code=f'CUST_{uid()}')
            event = Event.objects.create(
                customer=customer,
                action='purchase',
                description='Test purchase event',
            )
            self.assertEqual(event.action, 'purchase')
        except Exception as e:
            self.fail(f"Event creation failed: {e}")

    def test_event_without_customer(self):
        from api.djoyalty.models import Event
        try:
            event = Event.objects.create(
                customer=None,
                action='system_event',
            )
            self.assertIsNone(event.customer)
        except Exception as e:
            self.fail(f"Event without customer failed: {e}")

    def test_custom_managers(self):
        from api.djoyalty.models import Customer, Txn
        try:
            customer = Customer.objects.create(code=f'CUST_{uid()}')
            Txn.objects.create(customer=customer, value=100.00, is_discount=False)
            Txn.objects.create(customer=customer, value=50.00, is_discount=True)

            full_count = Txn.txn_full.count()
            discount_count = Txn.txn_discount.count()
            self.assertGreaterEqual(full_count, 1)
            self.assertGreaterEqual(discount_count, 1)
        except Exception as e:
            self.fail(f"Custom managers test failed: {e}")