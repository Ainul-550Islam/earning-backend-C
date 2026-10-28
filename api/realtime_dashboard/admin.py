"""
Django admin configuration for Real-time Dashboard Backend.

DRY FIX: activate() and deactivate() methods were copy-pasted identically
into DashboardWidgetAdmin, RealTimeMetricAdmin, and UserDashboardAdmin
(~30 lines × 3 = 90 lines of duplication). Extracted into StatusActionMixin
which each admin class now inherits.

The mixin uses short_descriptions as class attributes so Django admin
shows the correct action labels in the action dropdown.
"""
from typing import TYPE_CHECKING

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models.dashboard_widget import DashboardWidget
from .models.widget_configuration import WidgetConfiguration
from .models.real_time_metric import RealTimeMetric
from .models.dashboard_layout import DashboardLayout
from .models.user_dashboard import UserDashboard
from .models.websocket_connection import WebSocketConnection

# MYPY FIX (v9): every real usage of this mixin combines it with
# admin.ModelAdmin (see the docstring example, and every class below), but
# the mixin itself doesn't inherit from anything, so mypy has no way to know
# self.message_user() exists when it type-checks activate()/deactivate() in
# isolation. TYPE_CHECKING-only base gives mypy the full picture without
# touching runtime MRO — _MixinBase is `object` at runtime, identical to
# the mixin's previous bare `class StatusActionMixin:` behavior.
if TYPE_CHECKING:
    _MixinBase = admin.ModelAdmin
else:
    _MixinBase = object


class StatusActionMixin(_MixinBase):
    """
    DRY mixin adding activate() and deactivate() bulk admin actions.

    Any ModelAdmin subclass that mixes this in gets both actions for free.
    The model must have a `status` field that accepts 'active'/'inactive'.

    Usage:
        class MyModelAdmin(StatusActionMixin, admin.ModelAdmin):
            actions = ['activate', 'deactivate']
    """

    @admin.action(description=_('Activate selected items'))
    def activate(self, request, queryset):
        count = queryset.update(status='active')
        self.message_user(request, _(f'{count} item(s) activated.'))

    @admin.action(description=_('Deactivate selected items'))
    def deactivate(self, request, queryset):
        count = queryset.update(status='inactive')
        self.message_user(request, _(f'{count} item(s) deactivated.'))


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(StatusActionMixin, admin.ModelAdmin):
    """Admin view for DashboardWidget."""

    list_display = ['name', 'widget_type', 'status', 'refresh_interval', 'width', 'height', 'created_at']
    list_filter = ['widget_type', 'status']
    search_fields = ['name', 'description', 'created_by']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['activate', 'deactivate']
    list_select_related = True
    ordering = ['-created_at']


@admin.register(WidgetConfiguration)
class WidgetConfigurationAdmin(admin.ModelAdmin):
    """Admin view for WidgetConfiguration."""

    list_display = ['key', 'config_type', 'widget', 'created_at']
    list_filter = ['config_type']
    search_fields = ['key', 'widget__name']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['widget']


@admin.register(RealTimeMetric)
class RealTimeMetricAdmin(StatusActionMixin, admin.ModelAdmin):
    """Admin view for RealTimeMetric."""

    list_display = [
        'name', 'metric_type', 'status', 'value', 'unit',
        'warning_threshold', 'critical_threshold', 'last_updated',
    ]
    list_filter = ['metric_type', 'status']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'last_updated']
    actions = ['activate', 'deactivate']
    ordering = ['-last_updated']


@admin.register(DashboardLayout)
class DashboardLayoutAdmin(admin.ModelAdmin):
    """Admin view for DashboardLayout."""

    list_display = ['name', 'layout_type', 'columns', 'rows', 'created_at']
    list_filter = ['layout_type']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserDashboard)
class UserDashboardAdmin(StatusActionMixin, admin.ModelAdmin):
    """Admin view for UserDashboard."""

    list_display = ['name', 'user_id', 'status', 'layout', 'created_at']
    list_filter = ['status']
    search_fields = ['name', 'user_id']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['activate', 'deactivate']
    list_select_related = ['layout']


@admin.register(WebSocketConnection)
class WebSocketConnectionAdmin(admin.ModelAdmin):
    """Admin view for WebSocketConnection."""

    list_display = ['connection_id', 'user_id', 'status', 'connected_at', 'last_ping']
    list_filter = ['status']
    search_fields = ['connection_id', 'user_id', 'session_id']
    readonly_fields = ['connected_at', 'last_ping']
    ordering = ['-connected_at']
