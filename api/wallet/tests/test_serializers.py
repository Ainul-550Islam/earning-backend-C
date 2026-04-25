# api/wallet/tests/test_serializers.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, WalletTransaction, WithdrawalRequest, WithdrawalMethod
from ..services import WalletService
from ..serializers import (WalletSerializer, WalletTransactionSerializer,
    WithdrawalRequestSerializer, WithdrawalMethodSerializer)

User = get_user_model()


class SerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sertest", password="pass", email="ser@test.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("500")
        self.wallet.save()

    def test_wallet_serializer_fields(self):
        s = WalletSerializer(self.wallet)
        data = s.data
        self.assertIn("current_balance", data)
        self.assertIn("available_balance", data)
        self.assertIn("total_balance", data)
        self.assertIn("username", data)
        self.assertIn("version", data)

    def test_wallet_serializer_available_balance(self):
        self.wallet.frozen_balance = Decimal("100")
        self.wallet.save()
        s = WalletSerializer(self.wallet)
        self.assertEqual(s.data["available_balance"], "400.00000000")

    def test_transaction_serializer_has_txn_id(self):
        txn = WalletTransaction.objects.create(
            wallet=self.wallet, type="earning", amount=Decimal("100"),
            status="approved", balance_before=Decimal("500"),
        )
        s = WalletTransactionSerializer(txn)
        self.assertIn("transaction_id", s.data)
        self.assertIn("type_display", s.data)

    def test_withdrawal_method_serializer_masks_account(self):
        pm = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01712345678", account_name="Test",
        )
        s = WithdrawalMethodSerializer(pm)
        self.assertEqual(s.data["masked_account"], "****5678")

    def test_withdrawal_amount_validation_min(self):
        pm = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01712345678", account_name="Test",
        )
        s = WithdrawalRequestSerializer(data={
            "user": self.user.id, "wallet": self.wallet.id,
            "payment_method": pm.id, "amount": "10",
        })
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)
