"""filters.py – django-filter FilterSets for subscription viewsets."""
import django_filters as filters

from .choices import (
    PaymentMethod,
    PaymentStatus,
    PlanInterval,
    PlanStatus,
    SubscriptionStatus,
)
from .models import SubscriptionPayment, SubscriptionPlan, UserSubscription


class SubscriptionPlanFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=PlanStatus.choices)
    interval = filters.ChoiceFilter(choices=PlanInterval.choices)
    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    is_featured = filters.BooleanFilter()
    currency = filters.CharFilter(lookup_expr="iexact")
    search = filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = SubscriptionPlan
        fields = ["status", "interval", "currency", "is_featured"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(name__icontains=value) | queryset.filter(
            description__icontains=value
        )


class UserSubscriptionFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=SubscriptionStatus.choices)
    plan = filters.UUIDFilter(field_name="plan__id")
    plan_name = filters.CharFilter(field_name="plan__name", lookup_expr="icontains")
    user = filters.NumberFilter(field_name="user__id")
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    expires_before = filters.DateTimeFilter(field_name="current_period_end", lookup_expr="lte")
    cancel_at_period_end = filters.BooleanFilter()

    class Meta:
        model = UserSubscription
        fields = ["status", "plan", "cancel_at_period_end"]


class SubscriptionPaymentFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=PaymentStatus.choices)
    payment_method = filters.ChoiceFilter(choices=PaymentMethod.choices)
    currency = filters.CharFilter(lookup_expr="iexact")
    min_amount = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = filters.NumberFilter(field_name="amount", lookup_expr="lte")
    paid_after = filters.DateTimeFilter(field_name="paid_at", lookup_expr="gte")
    paid_before = filters.DateTimeFilter(field_name="paid_at", lookup_expr="lte")
    subscription = filters.UUIDFilter(field_name="subscription__id")
    transaction_id = filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = SubscriptionPayment
        fields = ["status", "payment_method", "currency", "subscription"]