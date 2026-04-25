# api/wallet/factories.py
"""
Test data factories using factory_boy.
pip install factory-boy Faker

Usage in tests:
    wallet = WalletFactory()
    txn    = WalletTransactionFactory(wallet=wallet, type="earning")
    wr     = WithdrawalRequestFactory(status="pending")
"""
import factory
from factory.django import DjangoModelFactory
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username   = factory.Sequence(lambda n: f"user_{n}")
    email      = factory.LazyAttribute(lambda o: f"{o.username}@test.com")
    is_active  = True
    password   = factory.PostGenerationMethodCall("set_password", "testpass123")


class AdminUserFactory(UserFactory):
    is_staff     = True
    is_superuser = True
    username     = factory.Sequence(lambda n: f"admin_{n}")


class WalletFactory(DjangoModelFactory):
    class Meta:
        try:
            from .models.core import Wallet
            model = Wallet
        except ImportError:
            model = None

    user             = factory.SubFactory(UserFactory)
    currency         = "BDT"
    current_balance  = factory.LazyFunction(lambda: Decimal("1000.00"))
    pending_balance  = Decimal("0")
    frozen_balance   = Decimal("0")
    bonus_balance    = Decimal("0")
    reserved_balance = Decimal("0")
    total_earned     = factory.LazyFunction(lambda: Decimal("1000.00"))
    total_withdrawn  = Decimal("0")
    is_locked        = False


class WalletTransactionFactory(DjangoModelFactory):
    class Meta:
        try:
            from .models.core import WalletTransaction
            model = WalletTransaction
        except ImportError:
            model = None

    wallet         = factory.SubFactory(WalletFactory)
    type           = "earning"
    amount         = factory.LazyFunction(lambda: Decimal("100.00"))
    status         = "approved"
    description    = factory.Faker("sentence")
    balance_before = Decimal("0")
    balance_after  = factory.LazyFunction(lambda: Decimal("100.00"))
    debit_account  = "revenue"
    credit_account = "user_balance"


class WithdrawalMethodFactory(DjangoModelFactory):
    class Meta:
        try:
            from .models.withdrawal import WithdrawalMethod
            model = WithdrawalMethod
        except ImportError:
            model = None

    user           = factory.SubFactory(UserFactory)
    method_type    = "bkash"
    account_number = factory.Sequence(lambda n: f"017{n:08d}")
    account_name   = factory.Faker("name")
    is_verified    = True
    is_default     = True


class WithdrawalRequestFactory(DjangoModelFactory):
    class Meta:
        try:
            from .models.withdrawal import WithdrawalRequest
            model = WithdrawalRequest
        except ImportError:
            model = None

    user           = factory.SubFactory(UserFactory)
    wallet         = factory.SubFactory(WalletFactory)
    payment_method = factory.SubFactory(WithdrawalMethodFactory)
    amount         = factory.LazyFunction(lambda: Decimal("500.00"))
    fee            = factory.LazyFunction(lambda: Decimal("10.00"))
    net_amount     = factory.LazyFunction(lambda: Decimal("490.00"))
    status         = "pending"
    currency       = "BDT"


class EarningRecordFactory(DjangoModelFactory):
    class Meta:
        try:
            from .models.earning import EarningRecord
            model = EarningRecord
        except ImportError:
            model = None

    wallet          = factory.SubFactory(WalletFactory)
    source_type     = "task"
    amount          = factory.LazyFunction(lambda: Decimal("50.00"))
    original_amount = factory.LazyFunction(lambda: Decimal("50.00"))
    country_code    = "BD"


class BalanceBonusFactory(DjangoModelFactory):
    class Meta:
        try:
            from .models.balance import BalanceBonus
            model = BalanceBonus
        except ImportError:
            model = None

    wallet  = factory.SubFactory(WalletFactory)
    amount  = factory.LazyFunction(lambda: Decimal("100.00"))
    source  = "admin"
    status  = "active"
