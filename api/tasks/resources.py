"""
api/tasks/resources.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Django Import/Export resource classes for the task system.
Enables CSV/XLSX bulk import and export via admin panel.
Requires: django-import-export

Usage in admin.py:
    from import_export.admin import ImportExportModelAdmin
    from api.tasks.resources import MasterTaskResource

    @admin.register(MasterTask)
    class MasterTaskAdmin(ImportExportModelAdmin):
        resource_class = MasterTaskResource
"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

try:
    from import_export import resources, fields
    from import_export.widgets import DecimalWidget, BooleanWidget, JSONWidget

    class MasterTaskResource(resources.ModelResource):
        """Import/Export resource for MasterTask."""

        class Meta:
            try:
                from api.tasks.models import MasterTask
                model = MasterTask
            except ImportError:
                model = None
            fields = (
                'id', 'task_id', 'name', 'category', 'system_type',
                'is_active', 'is_featured', 'sort_order',
            )
            export_order = fields
            import_id_fields = ('task_id',)

        def dehydrate_rewards(self, task):
            """Export rewards as JSON string."""
            import json
            return json.dumps(task.rewards or {})

        def before_import_row(self, row, **kwargs):
            """Clean row data before import."""
            row['is_active']   = str(row.get('is_active', 'true')).lower() == 'true'
            row['is_featured'] = str(row.get('is_featured', 'false')).lower() == 'true'


    class UserTaskCompletionResource(resources.ModelResource):
        """Import/Export resource for UserTaskCompletion."""
        username    = fields.Field(column_name='username', attribute='user__username')
        task_id_str = fields.Field(column_name='task_id',  attribute='task__task_id')

        class Meta:
            try:
                from api.tasks.models import UserTaskCompletion
                model = UserTaskCompletion
            except ImportError:
                model = None
            fields = (
                'id', 'username', 'task_id_str', 'status',
                'reward_amount', 'ip_address', 'completed_at',
            )
            export_only = ('id', 'username', 'task_id_str', 'completed_at')


    class AdminLedgerResource(resources.ModelResource):
        """Read-only export resource for AdminLedger."""

        class Meta:
            try:
                from api.tasks.models import AdminLedger
                model = AdminLedger
            except ImportError:
                model = None
            fields = ('id', 'amount', 'source', 'created_at')
            export_only = fields

except ImportError:
    # django-import-export not installed — provide empty classes
    logger.debug("[RESOURCES] django-import-export not installed. Resources disabled.")

    class MasterTaskResource:              pass
    class UserTaskCompletionResource:     pass
    class AdminLedgerResource:            pass


__all__ = [
    'MasterTaskResource', 'UserTaskCompletionResource', 'AdminLedgerResource',
]
