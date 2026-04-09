# api/djoyalty/filters.py
"""
Django Filter (django-filter) classes for Djoyalty।
ViewSet এ filter_backends=[DjangoFilterBackend] দিয়ে ব্যবহার করো।

pip install django-filter (না থাকলে)
settings.py তে 'django_filters' যোগ করো।
"""

import logging
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

try:
    import django_filters
    from django_filters import rest_framework as filters
    FILTERS_AVAILABLE = True
except ImportError:
    FILTERS_AVAILABLE = False
    logger.warning(
        'django-filter not installed. Install it with: pip install django-filter'
    )


if FILTERS_AVAILABLE:

    # ==================== CUSTOMER FILTERS ====================

    class CustomerFilter(filters.FilterSet):
        """Customer list filter।"""

        code = django_filters.CharFilter(lookup_expr='iexact')
        firstname = django_filters.CharFilter(lookup_expr='icontains')
        lastname = django_filters.CharFilter(lookup_expr='icontains')
        email = django_filters.CharFilter(lookup_expr='icontains')
        phone = django_filters.CharFilter(lookup_expr='icontains')
        city = django_filters.CharFilter(lookup_expr='icontains')
        zip = django_filters.CharFilter(lookup_expr='iexact')
        newsletter = django_filters.BooleanFilter()
        created_at_after = django_filters.DateTimeFilter(
            field_name='created_at', lookup_expr='gte'
        )
        created_at_before = django_filters.DateTimeFilter(
            field_name='created_at', lookup_expr='lte'
        )
        search = django_filters.CharFilter(method='filter_search')

        def filter_search(self, queryset, name, value):
            return queryset.filter(
                Q(code__icontains=value)
                | Q(firstname__icontains=value)
                | Q(lastname__icontains=value)
                | Q(email__icontains=value)
                | Q(phone__icontains=value)
            )

        class Meta:
            try:
                from .models.core import Customer
                model = Customer
            except Exception:
                model = None
            fields = [
                'code', 'firstname', 'lastname', 'email',
                'phone', 'city', 'newsletter',
            ]


    # ==================== TXN FILTERS ====================

    class TxnFilter(filters.FilterSet):
        """Transaction list filter।"""

        customer = django_filters.NumberFilter(field_name='customer_id')
        customer_code = django_filters.CharFilter(
            field_name='customer__code', lookup_expr='iexact'
        )
        is_discount = django_filters.BooleanFilter()
        value_min = django_filters.NumberFilter(
            field_name='value', lookup_expr='gte'
        )
        value_max = django_filters.NumberFilter(
            field_name='value', lookup_expr='lte'
        )
        value_positive = django_filters.BooleanFilter(method='filter_positive_value')
        timestamp_after = django_filters.DateTimeFilter(
            field_name='timestamp', lookup_expr='gte'
        )
        timestamp_before = django_filters.DateTimeFilter(
            field_name='timestamp', lookup_expr='lte'
        )

        def filter_positive_value(self, queryset, name, value):
            if value:
                return queryset.filter(value__gt=0)
            return queryset.filter(value__lt=0)

        class Meta:
            try:
                from .models.core import Txn
                model = Txn
            except Exception:
                model = None
            fields = ['customer', 'is_discount']


    # ==================== EVENT FILTERS ====================

    class EventFilter(filters.FilterSet):
        """Event list filter।"""

        customer = django_filters.NumberFilter(field_name='customer_id')
        customer_code = django_filters.CharFilter(
            field_name='customer__code', lookup_expr='iexact'
        )
        action = django_filters.CharFilter(lookup_expr='iexact')
        action_contains = django_filters.CharFilter(
            field_name='action', lookup_expr='icontains'
        )
        is_anonymous = django_filters.BooleanFilter(method='filter_anonymous')
        timestamp_after = django_filters.DateTimeFilter(
            field_name='timestamp', lookup_expr='gte'
        )
        timestamp_before = django_filters.DateTimeFilter(
            field_name='timestamp', lookup_expr='lte'
        )

        def filter_anonymous(self, queryset, name, value):
            if value:
                return queryset.filter(customer__isnull=True)
            return queryset.filter(customer__isnull=False)

        class Meta:
            try:
                from .models.core import Event
                model = Event
            except Exception:
                model = None
            fields = ['customer', 'action']


    # ==================== POINTS LEDGER FILTERS ====================

    class PointsLedgerFilter(filters.FilterSet):
        """Points ledger filter।"""

        customer = django_filters.NumberFilter(field_name='customer_id')
        txn_type = django_filters.ChoiceFilter(
            choices=[('credit', 'Credit'), ('debit', 'Debit')]
        )
        source = django_filters.CharFilter(lookup_expr='iexact')
        points_min = django_filters.NumberFilter(
            field_name='points', lookup_expr='gte'
        )
        points_max = django_filters.NumberFilter(
            field_name='points', lookup_expr='lte'
        )
        is_expiring = django_filters.BooleanFilter(method='filter_expiring')
        is_expired = django_filters.BooleanFilter(method='filter_expired')
        created_after = django_filters.DateTimeFilter(
            field_name='created_at', lookup_expr='gte'
        )
        created_before = django_filters.DateTimeFilter(
            field_name='created_at', lookup_expr='lte'
        )

        def filter_expiring(self, queryset, name, value):
            from .constants import POINTS_EXPIRY_WARNING_DAYS
            from datetime import timedelta
            if value:
                warning_date = timezone.now() + timedelta(days=POINTS_EXPIRY_WARNING_DAYS)
                return queryset.filter(
                    expires_at__isnull=False,
                    expires_at__lte=warning_date,
                    expires_at__gt=timezone.now(),
                )
            return queryset

        def filter_expired(self, queryset, name, value):
            if value:
                return queryset.filter(
                    expires_at__isnull=False,
                    expires_at__lte=timezone.now(),
                )
            return queryset.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
            )

        class Meta:
            model = None  # points model এ set করা হবে
            fields = ['customer', 'txn_type', 'source']


    # ==================== EARN RULE FILTERS ====================

    class EarnRuleFilter(filters.FilterSet):
        """Earn rule filter।"""

        is_active = django_filters.BooleanFilter()
        rule_type = django_filters.CharFilter(lookup_expr='iexact')
        trigger = django_filters.CharFilter(lookup_expr='iexact')
        valid_now = django_filters.BooleanFilter(method='filter_valid_now')

        def filter_valid_now(self, queryset, name, value):
            if value:
                now = timezone.now()
                return queryset.filter(
                    is_active=True,
                ).filter(
                    Q(valid_from__isnull=True) | Q(valid_from__lte=now)
                ).filter(
                    Q(valid_until__isnull=True) | Q(valid_until__gte=now)
                )
            return queryset

        class Meta:
            model = None
            fields = ['is_active', 'rule_type', 'trigger']


    # ==================== REDEMPTION FILTERS ====================

    class RedemptionFilter(filters.FilterSet):
        """Redemption request filter।"""

        customer = django_filters.NumberFilter(field_name='customer_id')
        status = django_filters.CharFilter(lookup_expr='iexact')
        redemption_type = django_filters.CharFilter(lookup_expr='iexact')
        points_min = django_filters.NumberFilter(
            field_name='points_used', lookup_expr='gte'
        )
        points_max = django_filters.NumberFilter(
            field_name='points_used', lookup_expr='lte'
        )
        created_after = django_filters.DateTimeFilter(
            field_name='created_at', lookup_expr='gte'
        )
        created_before = django_filters.DateTimeFilter(
            field_name='created_at', lookup_expr='lte'
        )
        is_pending = django_filters.BooleanFilter(method='filter_pending')

        def filter_pending(self, queryset, name, value):
            if value:
                return queryset.filter(status='pending')
            return queryset.exclude(status='pending')

        class Meta:
            model = None
            fields = ['customer', 'status', 'redemption_type']


    # ==================== VOUCHER FILTERS ====================

    class VoucherFilter(filters.FilterSet):
        """Voucher filter।"""

        code = django_filters.CharFilter(lookup_expr='iexact')
        status = django_filters.CharFilter(lookup_expr='iexact')
        voucher_type = django_filters.CharFilter(lookup_expr='iexact')
        customer = django_filters.NumberFilter(field_name='customer_id')
        is_active = django_filters.BooleanFilter(method='filter_active')
        expires_after = django_filters.DateTimeFilter(
            field_name='expires_at', lookup_expr='gte'
        )
        expires_before = django_filters.DateTimeFilter(
            field_name='expires_at', lookup_expr='lte'
        )

        def filter_active(self, queryset, name, value):
            if value:
                return queryset.filter(
                    status='active',
                ).filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
                )
            return queryset

        class Meta:
            model = None
            fields = ['code', 'status', 'voucher_type', 'customer']


    # ==================== CAMPAIGN FILTERS ====================

    class CampaignFilter(filters.FilterSet):
        """Campaign filter।"""

        status = django_filters.CharFilter(lookup_expr='iexact')
        campaign_type = django_filters.CharFilter(lookup_expr='iexact')
        is_active = django_filters.BooleanFilter(method='filter_active')
        starts_after = django_filters.DateTimeFilter(
            field_name='start_date', lookup_expr='gte'
        )
        ends_before = django_filters.DateTimeFilter(
            field_name='end_date', lookup_expr='lte'
        )

        def filter_active(self, queryset, name, value):
            if value:
                now = timezone.now()
                return queryset.filter(
                    status='active',
                    start_date__lte=now,
                ).filter(
                    Q(end_date__isnull=True) | Q(end_date__gte=now)
                )
            return queryset

        class Meta:
            model = None
            fields = ['status', 'campaign_type']


    # ==================== TIER FILTERS ====================

    class LoyaltyTierFilter(filters.FilterSet):
        """Loyalty tier filter।"""

        name = django_filters.CharFilter(lookup_expr='iexact')
        is_active = django_filters.BooleanFilter()
        min_points_gte = django_filters.NumberFilter(
            field_name='min_points', lookup_expr='gte'
        )
        max_points_lte = django_filters.NumberFilter(
            field_name='max_points', lookup_expr='lte'
        )

        class Meta:
            model = None
            fields = ['name', 'is_active']


    # ==================== BADGE FILTERS ====================

    class BadgeFilter(filters.FilterSet):
        """Badge filter।"""

        trigger = django_filters.CharFilter(lookup_expr='iexact')
        is_active = django_filters.BooleanFilter()
        name = django_filters.CharFilter(lookup_expr='icontains')

        class Meta:
            model = None
            fields = ['trigger', 'is_active']


    # ==================== CHALLENGE FILTERS ====================

    class ChallengeFilter(filters.FilterSet):
        """Challenge filter।"""

        status = django_filters.CharFilter(lookup_expr='iexact')
        challenge_type = django_filters.CharFilter(lookup_expr='iexact')
        is_active = django_filters.BooleanFilter(method='filter_active')

        def filter_active(self, queryset, name, value):
            if value:
                now = timezone.now()
                return queryset.filter(
                    status='active',
                    start_date__lte=now,
                ).filter(
                    Q(end_date__isnull=True) | Q(end_date__gte=now)
                )
            return queryset

        class Meta:
            model = None
            fields = ['status', 'challenge_type']


    # ==================== FRAUD FILTERS ====================

    class FraudLogFilter(filters.FilterSet):
        """Fraud log filter।"""

        customer = django_filters.NumberFilter(field_name='customer_id')
        risk_level = django_filters.CharFilter(lookup_expr='iexact')
        is_resolved = django_filters.BooleanFilter()
        created_after = django_filters.DateTimeFilter(
            field_name='created_at', lookup_expr='gte'
        )
        created_before = django_filters.DateTimeFilter(
            field_name='created_at', lookup_expr='lte'
        )

        class Meta:
            model = None
            fields = ['customer', 'risk_level', 'is_resolved']


else:
    # django-filter না থাকলে placeholder class
    class CustomerFilter:
        pass

    class TxnFilter:
        pass

    class EventFilter:
        pass

    class PointsLedgerFilter:
        pass

    class EarnRuleFilter:
        pass

    class RedemptionFilter:
        pass

    class VoucherFilter:
        pass

    class CampaignFilter:
        pass

    class LoyaltyTierFilter:
        pass

    class BadgeFilter:
        pass

    class ChallengeFilter:
        pass

    class FraudLogFilter:
        pass
