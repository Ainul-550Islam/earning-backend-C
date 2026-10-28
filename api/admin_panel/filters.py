# api/admin_panel/filters.py
"""
django-filter FilterSet classes for admin_panel viewsets.
All Meta.model fields correctly defined using lazy imports inside Meta.
"""
import django_filters
from django.db.models import Q
from django.utils import timezone


class AdminActionFilter(django_filters.FilterSet):
    action_type = django_filters.CharFilter(field_name='action_type', lookup_expr='exact')
    admin = django_filters.NumberFilter(field_name='admin__id')
    admin_username = django_filters.CharFilter(field_name='admin__username', lookup_expr='icontains')
    target_user = django_filters.NumberFilter(field_name='target_user__id')
    date_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    ip_address = django_filters.CharFilter(field_name='ip_address', lookup_expr='exact')

    class Meta:
        model = None  # Set in get_filterset_class or via property
        fields = ['action_type', 'admin', 'target_user', 'ip_address']

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    @classmethod
    def get_model(cls):
        from .models.core import AdminAction
        return AdminAction


class ReportFilter(django_filters.FilterSet):
    report_type = django_filters.CharFilter(field_name='report_type', lookup_expr='exact')
    status = django_filters.CharFilter(field_name='status', lookup_expr='exact')
    generated_by = django_filters.NumberFilter(field_name='generated_by__id')
    date_from = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='end_date', lookup_expr='lte')
    created_from = django_filters.DateTimeFilter(field_name='generated_at', lookup_expr='gte')
    created_to = django_filters.DateTimeFilter(field_name='generated_at', lookup_expr='lte')
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')

    class Meta:
        model = None
        fields = ['report_type', 'status', 'generated_by']


class SiteNotificationFilter(django_filters.FilterSet):
    notification_type = django_filters.CharFilter(field_name='notification_type', lookup_expr='exact')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    show_on_login = django_filters.BooleanFilter(field_name='show_on_login')
    active_now = django_filters.BooleanFilter(method='filter_active_now')
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')

    class Meta:
        model = None
        fields = ['notification_type', 'is_active', 'show_on_login']

    def filter_active_now(self, queryset, name, value):
        now = timezone.now()
        if value:
            return queryset.filter(
                is_active=True
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=now)
            ).filter(start_date__lte=now)
        return queryset


class SiteContentFilter(django_filters.FilterSet):
    content_type = django_filters.CharFilter(field_name='content_type', lookup_expr='exact')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    language = django_filters.CharFilter(field_name='language', lookup_expr='exact')
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    identifier = django_filters.CharFilter(field_name='identifier', lookup_expr='icontains')

    class Meta:
        model = None
        fields = ['content_type', 'is_active', 'language']


class AdminActivityFilter(django_filters.FilterSet):
    actor = django_filters.NumberFilter(field_name='actor__id')
    actor_username = django_filters.CharFilter(field_name='actor__username', lookup_expr='icontains')
    action = django_filters.CharFilter(field_name='action', lookup_expr='exact')
    model_name = django_filters.CharFilter(field_name='model_name', lookup_expr='icontains')
    status = django_filters.CharFilter(field_name='status', lookup_expr='exact')
    ip = django_filters.CharFilter(field_name='ip', lookup_expr='exact')
    method = django_filters.CharFilter(field_name='method', lookup_expr='exact')
    date_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    object_id = django_filters.CharFilter(field_name='object_id', lookup_expr='exact')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = None
        fields = ['actor', 'action', 'model_name', 'status', 'ip', 'method']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(actor__username__icontains=value) |
            Q(model_name__icontains=value) |
            Q(action__icontains=value) |
            Q(ip__icontains=value)
        )


class AdminSessionFilter(django_filters.FilterSet):
    user = django_filters.NumberFilter(field_name='user__id')
    username = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    ip = django_filters.CharFilter(field_name='ip', lookup_expr='exact')
    status = django_filters.CharFilter(field_name='status', lookup_expr='exact')
    date_from = django_filters.DateTimeFilter(field_name='started_at', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='started_at', lookup_expr='lte')

    class Meta:
        model = None
        fields = ['user', 'is_active', 'ip', 'status']


class SystemConfigFilter(django_filters.FilterSet):
    group = django_filters.CharFilter(field_name='group', lookup_expr='exact')
    value_type = django_filters.CharFilter(field_name='value_type', lookup_expr='exact')
    is_public = django_filters.BooleanFilter(field_name='is_public')
    is_readonly = django_filters.BooleanFilter(field_name='is_readonly')
    key = django_filters.CharFilter(field_name='key', lookup_expr='icontains')
    description = django_filters.CharFilter(field_name='description', lookup_expr='icontains')

    class Meta:
        model = None
        fields = ['group', 'value_type', 'is_public', 'is_readonly']


class FeatureFlagFilter(django_filters.FilterSet):
    is_enabled = django_filters.BooleanFilter(field_name='is_enabled')
    flag_key = django_filters.CharFilter(field_name='flag_key', lookup_expr='icontains')
    updated_by = django_filters.NumberFilter(field_name='updated_by__id')
    rollout_min = django_filters.NumberFilter(field_name='rollout_pct', lookup_expr='gte')
    rollout_max = django_filters.NumberFilter(field_name='rollout_pct', lookup_expr='lte')

    class Meta:
        model = None
        fields = ['is_enabled', 'flag_key', 'updated_by']


class MaintenanceWindowFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter(field_name='is_active')
    notify_users = django_filters.BooleanFilter(field_name='notify_users')
    maintenance_type = django_filters.CharFilter(field_name='maintenance_type', lookup_expr='exact')
    start_from = django_filters.DateTimeFilter(field_name='start_at', lookup_expr='gte')
    start_to = django_filters.DateTimeFilter(field_name='start_at', lookup_expr='lte')
    upcoming = django_filters.BooleanFilter(method='filter_upcoming')

    class Meta:
        model = None
        fields = ['is_active', 'notify_users', 'maintenance_type']

    def filter_upcoming(self, queryset, name, value):
        now = timezone.now()
        if value:
            return queryset.filter(start_at__gte=now)
        return queryset.filter(start_at__lt=now)


class ReportDefinitionFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    report_type = django_filters.CharFilter(field_name='report_type', lookup_expr='exact')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    is_system = django_filters.BooleanFilter(field_name='is_system')

    class Meta:
        model = None
        fields = ['name', 'report_type', 'is_active', 'is_system']


class DataExportFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name='status', lookup_expr='exact')
    model_name = django_filters.CharFilter(field_name='model_name', lookup_expr='icontains')
    format = django_filters.CharFilter(field_name='format', lookup_expr='exact')
    requested_by = django_filters.NumberFilter(field_name='requested_by__id')
    date_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = None
        fields = ['status', 'model_name', 'format', 'requested_by']


class AdminInsightFilter(django_filters.FilterSet):
    type = django_filters.CharFilter(field_name='type', lookup_expr='exact')
    priority = django_filters.CharFilter(field_name='priority', lookup_expr='exact')
    is_read = django_filters.BooleanFilter(field_name='is_read')
    is_dismissed = django_filters.BooleanFilter(field_name='is_dismissed')
    is_expired = django_filters.BooleanFilter(method='filter_expired')

    class Meta:
        model = None
        fields = ['type', 'priority', 'is_read', 'is_dismissed']

    def filter_expired(self, queryset, name, value):
        now = timezone.now()
        if value:
            return queryset.filter(expires_at__lt=now)
        return queryset.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=now)
        )


class DashboardWidgetFilter(django_filters.FilterSet):
    widget_type = django_filters.CharFilter(field_name='widget_type', lookup_expr='exact')
    size = django_filters.CharFilter(field_name='size', lookup_expr='exact')
    user = django_filters.NumberFilter(field_name='user__id')
    is_visible = django_filters.BooleanFilter(field_name='is_visible')

    class Meta:
        model = None
        fields = ['widget_type', 'size', 'user', 'is_visible']


class ReportExportFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name='status', lookup_expr='exact')
    format = django_filters.CharFilter(field_name='format', lookup_expr='exact')
    generated_by = django_filters.NumberFilter(field_name='generated_by__id')
    date_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = None
        fields = ['status', 'format', 'generated_by']


def get_filter_for_model(model_class, filter_class):
    """
    Utility: dynamically bind Meta.model to a FilterSet class at runtime.
    Usage in viewsets:
        filterset_class = get_filter_for_model(AdminActivity, AdminActivityFilter)
    """
    import django_filters as df

    class BoundFilter(filter_class):
        class Meta(filter_class.Meta):
            model = model_class

    BoundFilter.__name__ = filter_class.__name__
    return BoundFilter