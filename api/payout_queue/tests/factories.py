"""Payout Queue Test Factories — factory_boy factories."""
from __future__ import annotations
import uuid
from decimal import Decimal
import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..choices import (
    PayoutBatchStatus, PayoutItemStatus, PaymentGateway,
    PriorityLevel, BulkProcessLogStatus, WithdrawalPriorityReason,
)
from ..models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"pquser_{n:04d}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "testpass123!")
        obj = super()._create(model_class, *args, **kwargs)
        obj.set_password(password)
        obj.save()
        return obj


class StaffUserFactory(UserFactory):
    is_staff = True


class PayoutBatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PayoutBatch

    name = factory.Sequence(lambda n: f"Batch {n:04d}")
    gateway = PaymentGateway.BKASH
    status = PayoutBatchStatus.PENDING
    priority = PriorityLevel.NORMAL
    total_amount = Decimal("0.00")
    total_fee = Decimal("0.00")
    net_amount = Decimal("0.00")
    item_count = 0
    success_count = 0
    failure_count = 0
    created_by = factory.SubFactory(StaffUserFactory)
    metadata = factory.LazyFunction(dict)


class PayoutItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PayoutItem

    batch = factory.SubFactory(PayoutBatchFactory)
    user = factory.SubFactory(UserFactory)
    status = PayoutItemStatus.QUEUED
    gateway = PaymentGateway.BKASH
    account_number = factory.Sequence(lambda n: f"017{n:08d}")
    gross_amount = Decimal("500.00")
    fee_amount = Decimal("9.25")
    net_amount = Decimal("490.75")
    internal_reference = factory.LazyFunction(lambda: str(uuid.uuid4()))
    retry_count = 0
    metadata = factory.LazyFunction(dict)


class WithdrawalPriorityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WithdrawalPriority
        exclude = ["_saved"]

    user = factory.SubFactory(UserFactory)
    priority = PriorityLevel.NORMAL
    previous_priority = ""
    reason = WithdrawalPriorityReason.USER_REQUEST
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Bypass append-only guard for tests
        obj = model_class(*args, **kwargs)
        obj.full_clean()
        super(model_class, obj).save()
        return obj


class BulkProcessLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BulkProcessLog
        exclude = ["_saved"]

    batch = factory.SubFactory(PayoutBatchFactory)
    status = BulkProcessLogStatus.SUCCESS
    task_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    items_attempted = 10
    items_succeeded = 10
    items_failed = 0
    items_skipped = 0
    duration_ms = 1200
    total_amount_processed = Decimal("5000.00")
    extra_data = factory.LazyFunction(dict)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        obj = model_class(*args, **kwargs)
        obj.full_clean()
        super(model_class, obj).save()
        return obj
