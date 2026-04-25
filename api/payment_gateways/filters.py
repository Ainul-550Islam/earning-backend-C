# api/payment_gateways/filters.py
# Full django-filter FilterSets for all payment_gateways models

import django_filters
from django.db.models import Q
from django_filters import rest_framework as filters


# ── GatewayTransaction Filter ──────────────────────────────────────────────────
class TransactionFilter(filters.FilterSet):
    """
    Filter GatewayTransaction queryset.
    Supported: ?gateway=bkash&status=completed&amount_min=100&date_from=2025-01-01&search=REF
    """
    date_from      = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to        = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    amount_min     = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max     = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    completed_from = django_filters.DateFilter(field_name='completed_at', lookup_expr='date__gte')
    completed_to   = django_filters.DateFilter(field_name='completed_at', lookup_expr='date__lte')
    search         = django_filters.CharFilter(method='filter_search', label='Search reference_id or gateway_ref')
    user_email     = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    is_completed   = django_filters.BooleanFilter(method='filter_completed')
    has_fee        = django_filters.BooleanFilter(method='filter_has_fee')

    class Meta:
        from api.payment_gateways.models.core import GatewayTransaction
        model  = GatewayTransaction
        fields = {
            'status':           ['exact', 'in'],
            'gateway':          ['exact', 'in'],
            'transaction_type': ['exact', 'in'],
            'currency':         ['exact'],
        }

    def filter_search(self, qs, name, value):
        return qs.filter(
            Q(reference_id__icontains=value) |
            Q(gateway_reference__icontains=value) |
            Q(notes__icontains=value)
        )

    def filter_completed(self, qs, name, value):
        return qs.filter(status='completed') if value else qs.exclude(status='completed')

    def filter_has_fee(self, qs, name, value):
        return qs.filter(fee__gt=0) if value else qs.filter(fee=0)


# ── PayoutRequest Filter ───────────────────────────────────────────────────────
class PayoutRequestFilter(filters.FilterSet):
    """
    Filter PayoutRequest (withdrawal requests).
    Supported: ?status=pending&payout_method=bkash&amount_min=500&user_email=x@y.com
    """
    date_from      = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to        = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    processed_from = django_filters.DateFilter(field_name='processed_at', lookup_expr='date__gte')
    processed_to   = django_filters.DateFilter(field_name='processed_at', lookup_expr='date__lte')
    amount_min     = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max     = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    user_email     = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    search         = django_filters.CharFilter(method='filter_search')
    is_pending     = django_filters.BooleanFilter(method='filter_pending')

    class Meta:
        from api.payment_gateways.models.core import PayoutRequest
        model  = PayoutRequest
        fields = {
            'status':        ['exact', 'in'],
            'payout_method': ['exact', 'in'],
            'currency':      ['exact'],
        }

    def filter_search(self, qs, name, value):
        return qs.filter(
            Q(reference_id__icontains=value) |
            Q(account_number__icontains=value) |
            Q(account_name__icontains=value) |
            Q(gateway_reference__icontains=value)
        )

    def filter_pending(self, qs, name, value):
        return qs.filter(status__in=['pending', 'approved']) if value else qs


# ── DepositRequest Filter ──────────────────────────────────────────────────────
class DepositRequestFilter(filters.FilterSet):
    """Filter DepositRequest. Supported: ?gateway=bkash&status=completed&amount_min=100"""
    date_from      = django_filters.DateFilter(field_name='initiated_at', lookup_expr='date__gte')
    date_to        = django_filters.DateFilter(field_name='initiated_at', lookup_expr='date__lte')
    completed_from = django_filters.DateFilter(field_name='completed_at', lookup_expr='date__gte')
    completed_to   = django_filters.DateFilter(field_name='completed_at', lookup_expr='date__lte')
    amount_min     = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max     = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    user_email     = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    search         = django_filters.CharFilter(method='filter_search')
    is_expired     = django_filters.BooleanFilter(method='filter_expired')

    class Meta:
        from api.payment_gateways.models.deposit import DepositRequest
        model  = DepositRequest
        fields = {
            'status':   ['exact', 'in'],
            'gateway':  ['exact', 'in'],
            'currency': ['exact'],
        }

    def filter_search(self, qs, name, value):
        return qs.filter(
            Q(reference_id__icontains=value) |
            Q(gateway_ref__icontains=value) |
            Q(session_key__icontains=value)
        )

    def filter_expired(self, qs, name, value):
        return qs.filter(status='expired') if value else qs.exclude(status='expired')


# ── DepositRefund Filter ───────────────────────────────────────────────────────
class DepositRefundFilter(filters.FilterSet):
    date_from  = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to    = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    amount_min = django_filters.NumberFilter(field_name='refund_amount', lookup_expr='gte')
    amount_max = django_filters.NumberFilter(field_name='refund_amount', lookup_expr='lte')
    user_email = django_filters.CharFilter(field_name='deposit__user__email', lookup_expr='icontains')

    class Meta:
        from api.payment_gateways.models.deposit import DepositRefund
        model  = DepositRefund
        fields = {'status': ['exact', 'in'], 'reason': ['exact']}


# ── PaymentGateway Filter ──────────────────────────────────────────────────────
class PaymentGatewayFilter(filters.FilterSet):
    """Filter PaymentGateway admin list."""
    region              = django_filters.CharFilter(lookup_expr='exact')
    supports_deposit    = django_filters.BooleanFilter()
    supports_withdrawal = django_filters.BooleanFilter()
    health_status       = django_filters.CharFilter(lookup_expr='exact')
    is_test_mode        = django_filters.BooleanFilter()

    class Meta:
        from api.payment_gateways.models.core import PaymentGateway
        model  = PaymentGateway
        fields = {
            'status': ['exact', 'in'],
            'name':   ['exact', 'in'],
        }


# ── ReconciliationBatch Filter ─────────────────────────────────────────────────
class ReconciliationBatchFilter(filters.FilterSet):
    date_from    = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to      = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    gateway_name = django_filters.CharFilter(field_name='gateway__name', lookup_expr='exact')
    has_mismatch = django_filters.BooleanFilter(method='filter_mismatch')

    class Meta:
        from api.payment_gateways.models.reconciliation import ReconciliationBatch
        model  = ReconciliationBatch
        fields = {'status': ['exact', 'in']}

    def filter_mismatch(self, qs, name, value):
        return qs.filter(total_mismatched__gt=0) if value else qs.filter(total_mismatched=0)


# ── PaymentAnalytics Filter ────────────────────────────────────────────────────
class PaymentAnalyticsFilter(filters.FilterSet):
    date_from        = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to          = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    gateway_name     = django_filters.CharFilter(field_name='gateway__name', lookup_expr='exact')
    min_success_rate = django_filters.NumberFilter(field_name='success_rate', lookup_expr='gte')

    class Meta:
        from api.payment_gateways.models.reconciliation import PaymentAnalytics
        model  = PaymentAnalytics
        fields = {
            'transaction_type': ['exact'],
            'currency':         ['exact'],
        }


# ── Conversion Filter (tracking) ───────────────────────────────────────────────
class ConversionFilter(filters.FilterSet):
    """Filter conversions for publisher dashboard."""
    date_from        = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to          = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    payout_min       = django_filters.NumberFilter(field_name='payout', lookup_expr='gte')
    payout_max       = django_filters.NumberFilter(field_name='payout', lookup_expr='lte')
    country          = django_filters.CharFilter(field_name='country_code', lookup_expr='exact')
    offer_name       = django_filters.CharFilter(field_name='offer__name', lookup_expr='icontains')
    publisher_email  = django_filters.CharFilter(field_name='publisher__email', lookup_expr='icontains')
    is_paid          = django_filters.BooleanFilter(field_name='publisher_paid')
    search           = django_filters.CharFilter(method='filter_search')

    class Meta:
        try:
            from api.payment_gateways.tracking.models import Conversion
            model = Conversion
        except Exception:
            model = None
        fields = {
            'status':          ['exact', 'in'],
            'conversion_type': ['exact', 'in'],
            'currency':        ['exact'],
        }

    def filter_search(self, qs, name, value):
        return qs.filter(
            Q(conversion_id__icontains=value) |
            Q(click_id_raw__icontains=value)
        )


# ── Click Filter ───────────────────────────────────────────────────────────────
class ClickFilter(filters.FilterSet):
    """Filter clicks for publisher stats."""
    date_from     = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to       = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    country       = django_filters.CharFilter(field_name='country_code', lookup_expr='exact')
    is_fraud      = django_filters.BooleanFilter()
    is_bot        = django_filters.BooleanFilter()
    is_converted  = django_filters.BooleanFilter()
    device        = django_filters.CharFilter(field_name='device_type', lookup_expr='exact')

    class Meta:
        try:
            from api.payment_gateways.tracking.models import Click
            model = Click
        except Exception:
            model = None
        fields = {'is_fraud': ['exact'], 'is_bot': ['exact'], 'is_converted': ['exact']}


# ── Support Ticket Filter ──────────────────────────────────────────────────────
class SupportTicketFilter(filters.FilterSet):
    date_from  = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to    = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    user_email = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    search     = django_filters.CharFilter(method='filter_search')
    is_open    = django_filters.BooleanFilter(method='filter_open')

    class Meta:
        try:
            from api.payment_gateways.support.models import SupportTicket
            model = SupportTicket
        except Exception:
            model = None
        fields = {
            'status':   ['exact', 'in'],
            'category': ['exact'],
            'priority': ['exact'],
        }

    def filter_search(self, qs, name, value):
        return qs.filter(
            Q(ticket_number__icontains=value) |
            Q(subject__icontains=value) |
            Q(description__icontains=value)
        )

    def filter_open(self, qs, name, value):
        return qs.filter(status__in=['open', 'in_progress']) if value else qs


# ── SmartLink Filter ────────────────────────────────────────────────────────────
class SmartLinkFilter(filters.FilterSet):
    publisher_email = django_filters.CharFilter(
        field_name='publisher__email', lookup_expr='icontains',
    )
    has_conversions = django_filters.BooleanFilter(method='filter_conversions')

    class Meta:
        try:
            from api.payment_gateways.smartlink.models import SmartLink
            model = SmartLink
        except Exception:
            model = None
        fields = {
            'status':        ['exact'],
            'rotation_mode': ['exact'],
        }

    def filter_conversions(self, qs, name, value):
        return qs.filter(total_conversions__gt=0) if value else qs.filter(total_conversions=0)


# ── Offer Filter ───────────────────────────────────────────────────────────────
class OfferFilter(filters.FilterSet):
    """Filter offers for publisher feed."""
    payout_min      = django_filters.NumberFilter(field_name='publisher_payout', lookup_expr='gte')
    payout_max      = django_filters.NumberFilter(field_name='publisher_payout', lookup_expr='lte')
    country         = django_filters.CharFilter(method='filter_country')
    search          = django_filters.CharFilter(method='filter_search')
    advertiser_email= django_filters.CharFilter(
        field_name='advertiser__email', lookup_expr='icontains',
    )
    has_cap         = django_filters.BooleanFilter(method='filter_has_cap')

    class Meta:
        try:
            from api.payment_gateways.offers.models import Offer
            model = Offer
        except Exception:
            model = None
        fields = {
            'offer_type': ['exact', 'in'],
            'status':     ['exact', 'in'],
            'category':   ['exact'],
            'currency':   ['exact'],
        }

    def filter_country(self, qs, name, value):
        return qs.filter(
            Q(target_countries=[]) | Q(target_countries__contains=[value.upper()])
        ).exclude(blocked_countries__contains=[value.upper()])

    def filter_search(self, qs, name, value):
        return qs.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(category__icontains=value)
        )

    def filter_has_cap(self, qs, name, value):
        if value:
            return qs.filter(
                Q(daily_cap__isnull=False) | Q(total_cap__isnull=False)
            )
        return qs.filter(daily_cap__isnull=True, total_cap__isnull=True)
