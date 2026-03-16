from django_filters import rest_framework as filters
from django.db.models import Q
from .models import PostbackLog, NetworkPostbackConfig

class PostbackLogFilter(filters.FilterSet):
    # এখানে অবশ্যই 'filters.BooleanFilter' বা সঠিক টাইপ উল্লেখ করতে হবে
    has_user = filters.BooleanFilter(method="filter_has_user", label="Has Resolved User")

    class Meta:
        model = PostbackLog
        fields = ["status", "rejection_reason", "network", "signature_verified"]

    def filter_has_user(self, queryset, name, value):
        if value:
            return queryset.filter(resolved_user__isnull=False)
        return queryset.filter(resolved_user__isnull=True)


class NetworkPostbackConfigFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=[
        ("active", "Active"), ("inactive", "Inactive"), ("testing", "Testing")
    ])
    network_type = filters.ChoiceFilter(choices=[
        ("cpa", "CPA"), ("cpl", "CPL"), ("cpi", "CPI"),
        ("affiliate", "Affiliate"), ("direct", "Direct"), ("internal", "Internal"),
    ])
    search = filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = NetworkPostbackConfig
        fields = ["status", "network_type"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(network_key__icontains=value)
        )