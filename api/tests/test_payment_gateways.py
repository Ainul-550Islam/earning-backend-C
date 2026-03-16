# api/tests/test_payment_gateways.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class PaymentGatewayTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def test_gateway_creation(self):
        from api.payment_gateways.models import PaymentGateway
        gw = PaymentGateway.objects.create(
            name='bkash',
            display_name='bKash',
            status='active',
        )
        self.assertTrue(gw.is_available)

    def test_gateway_transaction(self):
        from api.payment_gateways.models import GatewayTransaction
        txn = GatewayTransaction.objects.create(
            user=self.user,
            transaction_type='deposit',
            gateway='bkash',
            amount=100.00,
            fee=2.00,
            net_amount=98.00,   # ✅ NOT NULL field - দিতে হবে
            status='pending',
            reference_id=f'REF_{uid()}',
        )
        self.assertEqual(txn.status, 'pending')