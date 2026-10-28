"""
Django-filter FilterSet classes for Real-time Dashboard Backend.

Each FilterSet maps to one model and is wired into the corresponding
viewset via `filterset_class`.

Register the filter backend globally in settings.py:

    REST_FRAMEWORK = {
        'DEFAULT_FILTER_BACKENDS': [
            'django_filters.rest_framework.DjangoFilterBackend',
            'rest_framework.filters.SearchFilter',
            'rest_framework.filters.OrderingFilter',
        ],
    }

Or override per-viewset with:
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

Usage examples:
    GET /api/widgets/?widget_type=chart&status=active
    GET /api/metrics/?metric_type=gauge&status=active&value_min=10
    GET /api/dashboards/?status=active&search=sales
    GET /api/connections/?status=connected
    GET /api/layouts/?layout_type=grid
    GET /api/widget-configurations/?widget=42&config_type=chart
"""
import django_filters

from .models.dashboard_widget import DashboardWidget
from .models.widget_configuration import WidgetConfiguration
from .models.real_time_metric import RealTimeMetric
from .models.dashboard_layout import DashboardLayout
from .models.user_dashboard import UserDashboard
from .models.websocket_connection import WebSocketConnection


class DashboardWidgetFilter(django_filters.FilterSet):
    """Filters for DashboardWidget list endpoint."""

    name = django_filters.CharFilter(lookup_expr='icontains', label='Name contains')
    widget_type = django_filters.ChoiceFilter(choices=DashboardWidget.WidgetType.choices)
    status = django_filters.ChoiceFilter(choices=DashboardWidget.WidgetStatus.choices)
    created_by = django_filters.CharFilter(lookup_expr='icontains', label='Created by contains')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    # Refresh interval range
    refresh_min = django_filters.NumberFilter(field_name='refresh_interval', lookup_expr='gte')
    refresh_max = django_filters.NumberFilter(field_name='refresh_interval', lookup_expr='lte')

    class Meta:
        model = DashboardWidget
        fields = ['widget_type', 'status', 'created_by']


class WidgetConfigurationFilter(django_filters.FilterSet):
    """Filters for WidgetConfiguration list endpoint."""

    widget = django_filters.NumberFilter(label='Widget ID')
    config_type = django_filters.ChoiceFilter(choices=WidgetConfiguration.ConfigType.choices)
    key = django_filters.CharFilter(lookup_expr='icontains', label='Key contains')

    class Meta:
        model = WidgetConfiguration
        fields = ['widget', 'config_type', 'key']


class RealTimeMetricFilter(django_filters.FilterSet):
    """Filters for RealTimeMetric list endpoint."""

    name = django_filters.CharFilter(lookup_expr='icontains', label='Name contains')
    metric_type = django_filters.ChoiceFilter(choices=RealTimeMetric.MetricType.choices)
    status = django_filters.ChoiceFilter(choices=RealTimeMetric.MetricStatus.choices)
    unit = django_filters.CharFilter(lookup_expr='iexact')
    # Value range filters — useful for threshold-based alerting queries.
    value_min = django_filters.NumberFilter(field_name='value', lookup_expr='gte')
    value_max = django_filters.NumberFilter(field_name='value', lookup_expr='lte')
    updated_after = django_filters.DateTimeFilter(field_name='last_updated', lookup_expr='gte')
    updated_before = django_filters.DateTimeFilter(field_name='last_updated', lookup_expr='lte')

    class Meta:
        model = RealTimeMetric
        fields = ['metric_type', 'status', 'unit']


class DashboardLayoutFilter(django_filters.FilterSet):
    """Filters for DashboardLayout list endpoint."""

    name = django_filters.CharFilter(lookup_expr='icontains', label='Name contains')
    layout_type = django_filters.ChoiceFilter(choices=DashboardLayout.LayoutType.choices)
    created_by = django_filters.CharFilter(lookup_expr='icontains', label='Created by contains')

    class Meta:
        model = DashboardLayout
        fields = ['layout_type', 'created_by']


class UserDashboardFilter(django_filters.FilterSet):
    """
    Filters for UserDashboard list endpoint.

    Note: user_id filtering is intentionally excluded here because
    UserDashboardViewSet.get_queryset() already scopes results to
    request.user. Allowing ?user_id= on the list endpoint would be
    confusing (it would be silently overridden by get_queryset).
    Staff can use the /by_user/ action for cross-user queries.
    """

    name = django_filters.CharFilter(lookup_expr='icontains', label='Name contains')
    status = django_filters.ChoiceFilter(choices=UserDashboard.DashboardStatus.choices)
    has_layout = django_filters.BooleanFilter(
        field_name='layout',
        lookup_expr='isnull',
        label='Has layout',
        # BooleanFilter with isnull: True means layout IS NULL, so we
        # invert — True → has_layout → exclude nulls.
        exclude=True,
    )
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = UserDashboard
        fields = ['status']


class WebSocketConnectionFilter(django_filters.FilterSet):
    """Filters for WebSocketConnection list endpoint."""

    status = django_filters.ChoiceFilter(choices=WebSocketConnection.ConnectionStatus.choices)
    # Admins use the by_user action; this filter is here so staff can
    # additionally filter the scoped list by session.
    session_id = django_filters.CharFilter(lookup_expr='iexact')
    connected_after = django_filters.DateTimeFilter(field_name='connected_at', lookup_expr='gte')
    connected_before = django_filters.DateTimeFilter(field_name='connected_at', lookup_expr='lte')

    class Meta:
        model = WebSocketConnection
        fields = ['status', 'session_id']
