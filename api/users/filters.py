"""
api/users/filters.py
DjangoFilterBackend filters for user endpoints
pip install django-filter
"""
import django_filters
from django.contrib.auth import get_user_model
from .constants import UserStatus, UserTier, UserRole

User = get_user_model()


class UserFilter(django_filters.FilterSet):
    """Admin user list filter"""

    # Text search
    search       = django_filters.CharFilter(method='filter_search', label='Search')
    username     = django_filters.CharFilter(lookup_expr='icontains')
    email        = django_filters.CharFilter(lookup_expr='icontains')
    phone        = django_filters.CharFilter(field_name='phone', lookup_expr='icontains')

    # Exact match
    tier         = django_filters.ChoiceFilter(choices=UserTier.CHOICES)
    role         = django_filters.ChoiceFilter(choices=UserRole.CHOICES)
    is_active    = django_filters.BooleanFilter()
    is_verified  = django_filters.BooleanFilter()
    country      = django_filters.CharFilter(lookup_expr='iexact')

    # Date range
    joined_from  = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    joined_to    = django_filters.DateFilter(field_name='created_at', lookup_expr='lte')

    # Balance range
    balance_min  = django_filters.NumberFilter(field_name='balance', lookup_expr='gte')
    balance_max  = django_filters.NumberFilter(field_name='balance', lookup_expr='lte')

    # Earning range
    earned_min   = django_filters.NumberFilter(field_name='total_earned', lookup_expr='gte')
    earned_max   = django_filters.NumberFilter(field_name='total_earned', lookup_expr='lte')

    # Referral
    has_referrals= django_filters.BooleanFilter(method='filter_has_referrals')
    referred_by  = django_filters.UUIDFilter(field_name='referred_by__id')

    class Meta:
        model  = User
        fields = [
            'username', 'email', 'tier', 'role',
            'is_active', 'is_verified', 'country',
        ]

    def filter_search(self, queryset, name, value):
        """username, email, phone-এ একসাথে search"""
        from django.db.models import Q
        return queryset.filter(
            Q(username__icontains=value) |
            Q(email__icontains=value)    |
            Q(phone__icontains=value)
        )

    def filter_has_referrals(self, queryset, name, value):
        if value:
            return queryset.filter(referrals_list__isnull=False).distinct()
        return queryset.filter(referrals_list__isnull=True)


class UserActivityFilter(django_filters.FilterSet):
    """User activity log filter"""
    activity_type = django_filters.CharFilter(lookup_expr='iexact')
    from_date     = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    to_date       = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    ip_address    = django_filters.CharFilter(lookup_expr='iexact')

    class Meta:
        from .models import UserActivity
        model  = UserActivity
        fields = ['activity_type', 'ip_address']
