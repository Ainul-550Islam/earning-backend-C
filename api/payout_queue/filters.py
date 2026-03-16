"""Payout Queue Filters"""
import django_filters
from .choices import PayoutBatchStatus, PayoutItemStatus, PaymentGateway, PriorityLevel, BulkProcessLogStatus
from .models import PayoutBatch, PayoutItem, BulkProcessLog


class PayoutBatchFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=PayoutBatchStatus.choices)
    gateway = django_filters.ChoiceFilter(choices=PaymentGateway.choices)
    priority = django_filters.ChoiceFilter(choices=PriorityLevel.choices)
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = PayoutBatch
        fields = ["status", "gateway", "priority"]


class PayoutItemFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=PayoutItemStatus.choices)
    gateway = django_filters.ChoiceFilter(choices=PaymentGateway.choices)
    batch = django_filters.UUIDFilter()
    user = django_filters.NumberFilter()

    class Meta:
        model = PayoutItem
        fields = ["status", "gateway", "batch", "user"]


class BulkProcessLogFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=BulkProcessLogStatus.choices)
    batch = django_filters.UUIDFilter()

    class Meta:
        model = BulkProcessLog
        fields = ["status", "batch"]
