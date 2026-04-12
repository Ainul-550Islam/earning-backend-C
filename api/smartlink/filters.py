import django_filters
from django.db.models import Q
from .models.smartlink import SmartLink
from .models.click import Click
from .models.analytics import SmartLinkStat, SmartLinkDailyStat
from .choices import SmartLinkType, DeviceType


class SmartLinkFilter(django_filters.FilterSet):
    slug = django_filters.CharFilter(lookup_expr='icontains')
    type = django_filters.ChoiceFilter(choices=SmartLinkType.choices)
    is_active = django_filters.BooleanFilter()
    publisher = django_filters.NumberFilter(field_name='publisher__id')
    group = django_filters.NumberFilter(field_name='group__id')
    tag = django_filters.CharFilter(field_name='tags__name', lookup_expr='iexact')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    search = django_filters.CharFilter(method='search_filter')

    class Meta:
        model = SmartLink
        fields = ['slug', 'type', 'is_active', 'publisher', 'group', 'tag']

    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(slug__icontains=value) |
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class ClickFilter(django_filters.FilterSet):
    smartlink = django_filters.NumberFilter(field_name='smartlink__id')
    offer = django_filters.NumberFilter(field_name='offer__id')
    country = django_filters.CharFilter(lookup_expr='iexact')
    device_type = django_filters.ChoiceFilter(choices=DeviceType.choices)
    is_fraud = django_filters.BooleanFilter()
    is_bot = django_filters.BooleanFilter()
    is_unique = django_filters.BooleanFilter()
    date_from = django_filters.DateFilter(field_name='created_at__date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='created_at__date', lookup_expr='lte')
    ip = django_filters.CharFilter(lookup_expr='exact')

    class Meta:
        model = Click
        fields = [
            'smartlink', 'offer', 'country', 'device_type',
            'is_fraud', 'is_bot', 'is_unique', 'ip'
        ]


class SmartLinkStatFilter(django_filters.FilterSet):
    smartlink = django_filters.NumberFilter(field_name='smartlink__id')
    date = django_filters.DateFilter(field_name='hour__date')
    date_from = django_filters.DateFilter(field_name='hour__date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='hour__date', lookup_expr='lte')
    country = django_filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = SmartLinkStat
        fields = ['smartlink', 'country']


class SmartLinkDailyStatFilter(django_filters.FilterSet):
    smartlink = django_filters.NumberFilter(field_name='smartlink__id')
    date = django_filters.DateFilter()
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    publisher = django_filters.NumberFilter(field_name='smartlink__publisher__id')

    class Meta:
        model = SmartLinkDailyStat
        fields = ['smartlink', 'date']
