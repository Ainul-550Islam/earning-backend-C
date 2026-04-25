# api/wallet/filters.py
import django_filters
from django.db.models import Q
from .choices import TransactionType, TransactionStatus, GatewayType, EarningSourceType, BalanceType


class WalletFilter(django_filters.FilterSet):
    username      = django_filters.CharFilter(field_name="user__username", lookup_expr="icontains")
    email         = django_filters.CharFilter(field_name="user__email",    lookup_expr="icontains")
    user_id       = django_filters.NumberFilter(field_name="user__id")
    min_balance   = django_filters.NumberFilter(field_name="current_balance", lookup_expr="gte")
    max_balance   = django_filters.NumberFilter(field_name="current_balance", lookup_expr="lte")
    is_locked     = django_filters.BooleanFilter(field_name="is_locked")
    currency      = django_filters.CharFilter(field_name="currency", lookup_expr="iexact")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before= django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    class Meta:
        from .models.core import Wallet
        model  = Wallet
        fields = ["is_locked", "currency"]


class WalletTransactionFilter(django_filters.FilterSet):
    type          = django_filters.MultipleChoiceFilter(choices=TransactionType.choices)
    status        = django_filters.MultipleChoiceFilter(choices=TransactionStatus.choices)
    min_amount    = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount    = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    credit_only   = django_filters.BooleanFilter(method="filter_credit")
    debit_only    = django_filters.BooleanFilter(method="filter_debit")
    reference_id  = django_filters.CharFilter(lookup_expr="icontains")
    is_reversed   = django_filters.BooleanFilter(field_name="is_reversed")
    wallet_id     = django_filters.NumberFilter(field_name="wallet__id")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before= django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    date          = django_filters.DateFilter(field_name="created_at__date")
    class Meta:
        from .models.core import WalletTransaction
        model  = WalletTransaction
        fields = ["type", "status", "is_reversed"]
    def filter_credit(self, qs, name, v): return qs.filter(amount__gt=0) if v else qs
    def filter_debit(self, qs, name, v):  return qs.filter(amount__lt=0) if v else qs


class WithdrawalFilter(django_filters.FilterSet):
    status        = django_filters.MultipleChoiceFilter(choices=[
        ("pending","Pending"),("approved","Approved"),("completed","Completed"),
        ("rejected","Rejected"),("cancelled","Cancelled"),
    ])
    min_amount    = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount    = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    username      = django_filters.CharFilter(field_name="user__username", lookup_expr="icontains")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before= django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    class Meta:
        from .models.withdrawal import WithdrawalRequest
        model  = WithdrawalRequest
        fields = ["status"]


class EarningRecordFilter(django_filters.FilterSet):
    source_type  = django_filters.MultipleChoiceFilter(choices=EarningSourceType.choices)
    min_amount   = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount   = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    wallet_id    = django_filters.NumberFilter(field_name="wallet__id")
    earned_after = django_filters.DateTimeFilter(field_name="earned_at", lookup_expr="gte")
    earned_before= django_filters.DateTimeFilter(field_name="earned_at", lookup_expr="lte")
    class Meta:
        from .models.earning import EarningRecord
        model  = EarningRecord
        fields = []


class BalanceHistoryFilter(django_filters.FilterSet):
    balance_type = django_filters.MultipleChoiceFilter(choices=BalanceType.choices)
    wallet_id    = django_filters.NumberFilter(field_name="wallet__id")
    credits_only = django_filters.BooleanFilter(method="filter_credits")
    debits_only  = django_filters.BooleanFilter(method="filter_debits")
    created_after= django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    class Meta:
        from .models.balance import BalanceHistory
        model  = BalanceHistory
        fields = ["balance_type"]
    def filter_credits(self, qs, n, v): return qs.filter(delta__gt=0) if v else qs
    def filter_debits(self, qs, n, v):  return qs.filter(delta__lt=0) if v else qs


class LedgerEntryFilter(django_filters.FilterSet):
    entry_type   = django_filters.ChoiceFilter(choices=[("debit","Debit"),("credit","Credit")])
    account      = django_filters.CharFilter(lookup_expr="icontains")
    wallet_id    = django_filters.NumberFilter(field_name="ledger__wallet__id")
    min_amount   = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount   = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    created_after= django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    class Meta:
        from .models.ledger import LedgerEntry
        model  = LedgerEntry
        fields = ["entry_type"]


class WalletInsightFilter(django_filters.FilterSet):
    date_after  = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    wallet_id   = django_filters.NumberFilter(field_name="wallet__id")
    class Meta:
        from .models.analytics import WalletInsight
        model  = WalletInsight
        fields = []


class LiabilityReportFilter(django_filters.FilterSet):
    date_after  = django_filters.DateFilter(field_name="report_date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="report_date", lookup_expr="lte")
    currency    = django_filters.CharFilter(lookup_expr="iexact")
    class Meta:
        from .models.analytics import LiabilityReport
        model  = LiabilityReport
        fields = ["currency"]


class EarningSummaryFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = None
        fields = []
