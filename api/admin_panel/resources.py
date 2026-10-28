# api/admin_panel/resources.py
"""
Django import-export Resources for admin_panel.
Allows bulk import/export via Django admin and CLI.
pip install django-import-export

"Do not summarize or skip any logic. Provide the full code."
"""
from __future__ import annotations
from typing import Any

try:
    from import_export import resources, fields
    from import_export.widgets import (
        ForeignKeyWidget, ManyToManyWidget, BooleanWidget,
        DateTimeWidget, DecimalWidget, IntegerWidget, CharWidget,
    )
    IMPORT_EXPORT_AVAILABLE = True
except ImportError:
    IMPORT_EXPORT_AVAILABLE = False
    # Provide stub classes so imports don't break
    class _Stub:
        def __init_subclass__(cls, **kwargs): pass
    resources = type('resources', (), {'ModelResource': _Stub, 'Resource': _Stub})()


import logging
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
logger = logging.getLogger(__name__)


if IMPORT_EXPORT_AVAILABLE:

    # ==================== SystemConfig Resource ====================

    class SystemConfigResource(resources.ModelResource):
        """Export/import SystemConfig — allows bulk config updates via CSV."""

        class Meta:
            model = None  # set at import time
            fields = ('id', 'key', 'value', 'value_type', 'group',
                      'label', 'description', 'is_public', 'is_readonly',
                      'created_at', 'updated_at')
            export_order = ('key', 'value', 'value_type', 'group',
                            'label', 'is_public', 'is_readonly')
            import_id_fields = ('key',)
            skip_unchanged = True
            report_skipped = True

        def before_import_row(self, row, row_number=None, **kwargs):
            """Validate key format before import."""
            key = row.get('key', '')
            if not key or not key.replace('_', '').isalnum():
                raise ValueError(f"Row {row_number}: Invalid config key '{key}'")

        def after_save_instance(self, instance, new, row_number=None, **kwargs):
            """Clear cache after saving."""
            from django.core.cache import cache
            cache.delete(f'admin_panel:config:{instance.key}')
            cache.delete(f'admin_panel:config_group:{instance.group}')

        @classmethod
        def get_model(cls):
            from api.admin_panel.models.config import SystemConfig
            return SystemConfig

    # ==================== FeatureFlag Resource ====================

    class FeatureFlagResource(resources.ModelResource):
        """Export/import FeatureFlag — bulk flag management."""

        class Meta:
            model = None
            fields = ('id', 'flag_key', 'label', 'description', 'is_enabled',
                      'rollout_pct', 'environments', 'allowed_user_ids',
                      'created_at', 'updated_at')
            import_id_fields = ('flag_key',)
            skip_unchanged = True
            export_order = ('flag_key', 'label', 'is_enabled', 'rollout_pct')

        def before_import_row(self, row, row_number=None, **kwargs):
            rollout = int(row.get('rollout_pct', 100))
            if not 0 <= rollout <= 100:
                raise ValueError(f"Row {row_number}: rollout_pct must be 0-100")

        def after_save_instance(self, instance, new, row_number=None, **kwargs):
            from django.core.cache import cache
            cache.delete(f'admin_panel:feature_flag:{instance.flag_key}')

        @classmethod
        def get_model(cls):
            from api.admin_panel.models.config import FeatureFlag
            return FeatureFlag

    # ==================== AdminActivity Resource (export only) ====================

    class AdminActivityResource(resources.ModelResource):
        """Export AdminActivity logs — for compliance/audit export."""

        actor_username = fields.Field(column_name='actor_username')
        actor_email    = fields.Field(column_name='actor_email')

        class Meta:
            model = None
            fields = ('id', 'actor_username', 'actor_email', 'action', 'model_name',
                      'object_id', 'object_repr', 'status', 'ip', 'method',
                      'response_code', 'path', 'created_at')
            export_order = ('created_at', 'actor_username', 'action', 'model_name',
                            'status', 'ip')

        def dehydrate_actor_username(self, obj):
            return obj.actor.username if obj.actor else 'system'

        def dehydrate_actor_email(self, obj):
            return obj.actor.email if obj.actor else ''

        def get_export_queryset(self, **kwargs):
            return super().get_export_queryset(**kwargs).select_related('actor')

        @classmethod
        def get_model(cls):
            from api.admin_panel.models.activity import AdminActivity
            return AdminActivity

    # ==================== SiteContent Resource ====================

    class SiteContentResource(resources.ModelResource):
        """Export/import SiteContent — CMS content bulk management."""

        class Meta:
            model = None
            fields = ('id', 'identifier', 'title', 'content', 'content_type',
                      'language', 'is_active', 'order', 'meta_title',
                      'meta_description', 'created_at', 'updated_at')
            import_id_fields = ('identifier', 'language')
            skip_unchanged = True
            export_order = ('identifier', 'title', 'content_type', 'language', 'is_active')

        @classmethod
        def get_model(cls):
            from api.admin_panel.models.core import SiteContent
            return SiteContent

    # ==================== SiteNotification Resource ====================

    class SiteNotificationResource(resources.ModelResource):
        """Export/import SiteNotification — bulk notification management."""

        class Meta:
            model = None
            fields = ('id', 'title', 'message', 'notification_type', 'is_active',
                      'show_on_login', 'priority', 'start_date', 'end_date')
            import_id_fields = ('id',)
            skip_unchanged = True

        @classmethod
        def get_model(cls):
            from api.admin_panel.models.core import SiteNotification
            return SiteNotification

    # ==================== EndpointToggle Resource ====================

    class EndpointToggleResource(resources.ModelResource):
        """Export/import EndpointToggle — bulk API endpoint management."""

        class Meta:
            model = None
            fields = ('id', 'path', 'method', 'group', 'label',
                      'is_enabled', 'disabled_message', 'created_at')
            import_id_fields = ('path', 'method')
            skip_unchanged = True
            export_order = ('group', 'path', 'method', 'is_enabled')

        @classmethod
        def get_model(cls):
            from api.admin_panel.endpoint_toggle import EndpointToggle
            return EndpointToggle

    # ==================== AdminSession Resource (export only) ====================

    class AdminSessionResource(resources.ModelResource):
        """Export AdminSession — for security audit."""

        user_username = fields.Field(column_name='user_username')

        class Meta:
            model = None
            fields = ('id', 'user_username', 'ip', 'user_agent', 'location',
                      'started_at', 'last_seen', 'ended_at', 'is_active', 'status')
            export_order = ('started_at', 'user_username', 'ip', 'status')

        def dehydrate_user_username(self, obj):
            return obj.user.username if obj.user else ''

        @classmethod
        def get_model(cls):
            from api.admin_panel.models.activity import AdminSession
            return AdminSession

    # ==================== ReportDefinition Resource ====================

    class ReportDefinitionResource(resources.ModelResource):
        """Export/import ReportDefinition — share report templates."""

        class Meta:
            model = None
            fields = ('id', 'name', 'report_type', 'description', 'columns',
                      'filters', 'allowed_formats', 'is_active', 'is_system')
            import_id_fields = ('name',)
            skip_unchanged = True

        @classmethod
        def get_model(cls):
            from api.admin_panel.models.reports import ReportDefinition
            return ReportDefinition


    # ==================== RESOURCE REGISTRY ====================

    RESOURCE_MAP = {
        'system_config':       SystemConfigResource,
        'feature_flag':        FeatureFlagResource,
        'admin_activity':      AdminActivityResource,
        'site_content':        SiteContentResource,
        'site_notification':   SiteNotificationResource,
        'endpoint_toggle':     EndpointToggleResource,
        'admin_session':       AdminSessionResource,
        'report_definition':   ReportDefinitionResource,
    }

    EXPORT_ONLY_RESOURCES = {'admin_activity', 'admin_session'}

    def get_resource(name: str):
        """Get a resource class by name."""
        cls = RESOURCE_MAP.get(name)
        if not cls:
            raise ValueError(f"Unknown resource: {name}. Available: {list(RESOURCE_MAP.keys())}")
        return cls

    def export_to_csv(resource_name: str, queryset=None) -> str:
        """Export a resource to CSV string."""
        import tablib
        cls = get_resource(resource_name)
        resource = cls()
        # Set model dynamically
        if hasattr(cls, 'get_model'):
            resource._meta.model = cls.get_model()
        if queryset is None:
            queryset = resource._meta.model.objects.all()
        dataset = resource.export(queryset)
        return dataset.csv

    def import_from_csv(resource_name: str, csv_data: str, dry_run: bool = True) -> dict:
        """Import a resource from CSV string."""
        if resource_name in EXPORT_ONLY_RESOURCES:
            raise ValueError(f"Resource '{resource_name}' is export-only.")
        import tablib
        cls = get_resource(resource_name)
        resource = cls()
        if hasattr(cls, 'get_model'):
            resource._meta.model = cls.get_model()
        dataset = tablib.Dataset().load(csv_data, headers=True)
        result = resource.import_data(dataset, dry_run=dry_run, raise_errors=False)
        return {
            'dry_run': dry_run,
            'totals': result.totals,
            'has_errors': result.has_errors(),
            'has_validation_errors': result.has_validation_errors(),
            'error_rows': [str(e) for e in result.invalid_rows[:10]],
        }

else:
    # Stubs when import_export is not installed
    RESOURCE_MAP = {}
    EXPORT_ONLY_RESOURCES = set()

    def get_resource(name: str):
        raise ImportError("django-import-export not installed. Run: pip install django-import-export")

    def export_to_csv(resource_name: str, queryset=None) -> str:
        raise ImportError("django-import-export not installed.")

    def import_from_csv(resource_name: str, csv_data: str, dry_run: bool = True) -> dict:
        raise ImportError("django-import-export not installed.")