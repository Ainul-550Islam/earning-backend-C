# earning_backend/api/notifications/resources.py
"""
Resources — Django Import/Export resource classes for admin bulk operations.
Allows importing/exporting notifications, templates, and campaign data via CSV/Excel.
"""
try:
    from import_export import resources, fields
    from import_export.widgets import ForeignKeyWidget, JSONWidget
    IMPORT_EXPORT_AVAILABLE = True
except ImportError:
    IMPORT_EXPORT_AVAILABLE = False
    resources = None

import logging
logger = logging.getLogger(__name__)


if IMPORT_EXPORT_AVAILABLE:
    from django.contrib.auth import get_user_model
    User = get_user_model()

    class NotificationTemplateResource(resources.ModelResource):
        """Import/export NotificationTemplate via CSV/Excel in Django admin."""
        created_by = fields.Field(column_name='created_by', attribute='created_by',
                                   widget=ForeignKeyWidget(User, 'username'))

        class Meta:
            from api.notifications.models import NotificationTemplate
            model = NotificationTemplate
            fields = ('id', 'name', 'template_type', 'channel', 'category',
                      'title_en', 'title_bn', 'message_en', 'message_bn',
                      'is_active', 'is_public', 'created_by')
            export_order = ('id', 'name', 'template_type', 'channel', 'category',
                            'title_en', 'message_en', 'is_active')
            import_id_fields = ['name']
            skip_unchanged = True

    class NotificationResource(resources.ModelResource):
        """Import/export Notification data."""
        user = fields.Field(column_name='user', attribute='user',
                            widget=ForeignKeyWidget(User, 'username'))

        class Meta:
            from api.notifications.models import Notification
            model = Notification
            fields = ('id', 'user', 'title', 'message', 'notification_type',
                      'channel', 'priority', 'is_read', 'is_sent', 'created_at')
            export_order = ('id', 'user', 'notification_type', 'channel',
                            'priority', 'title', 'is_read', 'is_sent', 'created_at')
            skip_unchanged = True

    class CampaignResource(resources.ModelResource):
        """Import/export NotificationCampaign data."""

        class Meta:
            from api.notifications.models import NotificationCampaign
            model = NotificationCampaign
            fields = ('id', 'name', 'status', 'sent_count', 'total_count',
                      'failed_count', 'created_at', 'completed_at')
            export_order = fields
            skip_unchanged = True


else:
    # Stubs when django-import-export is not installed
    class NotificationTemplateResource:
        pass

    class NotificationResource:
        pass

    class CampaignResource:
        pass

    logger.debug('resources.py: django-import-export not installed — resource classes are stubs.')
