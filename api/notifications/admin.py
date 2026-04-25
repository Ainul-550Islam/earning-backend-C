"""
Django Admin Configuration for Notifications
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from django.contrib.admin import AdminSite
import json

from .models import (
    Notification, NotificationTemplate, NotificationPreference,
    DeviceToken, NotificationCampaign, NotificationAnalytics,
    NotificationRule, NotificationFeedback, NotificationLog
)


class NotificationStatusFilter(admin.SimpleListFilter):
    """Filter notifications by status"""
    title = 'Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return Notification.STATUS_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class NotificationTypeFilter(admin.SimpleListFilter):
    """Filter notifications by type"""
    title = 'Type'
    parameter_name = 'notification_type'
    
    def lookups(self, request, model_admin):
        types = Notification.objects.values_list(
            'notification_type', 'notification_type'
        ).distinct().order_by('notification_type')
        return [(t[0], t[1]) for t in types]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(notification_type=self.value())
        return queryset


class NotificationPriorityFilter(admin.SimpleListFilter):
    """Filter notifications by priority"""
    title = 'Priority'
    parameter_name = 'priority'
    
    def lookups(self, request, model_admin):
        return Notification.PRIORITY_LEVELS
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(priority=self.value())
        return queryset


class NotificationChannelFilter(admin.SimpleListFilter):
    """Filter notifications by channel"""
    title = 'Channel'
    parameter_name = 'channel'
    
    def lookups(self, request, model_admin):
        return Notification.CHANNEL_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(channel=self.value())
        return queryset


class ReadStatusFilter(admin.SimpleListFilter):
    """Filter notifications by read status"""
    title = 'Read Status'
    parameter_name = 'is_read'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Read'),
            ('no', 'Unread'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(is_read=True)
        elif self.value() == 'no':
            return queryset.filter(is_read=False)
        return queryset


class DeliveryStatusFilter(admin.SimpleListFilter):
    """Filter notifications by delivery status"""
    title = 'Delivery Status'
    parameter_name = 'is_delivered'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Delivered'),
            ('no', 'Not Delivered'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(is_delivered=True)
        elif self.value() == 'no':
            return queryset.filter(is_delivered=False)
        return queryset


class ArchivedStatusFilter(admin.SimpleListFilter):
    """Filter notifications by archived status"""
    title = 'Archived Status'
    parameter_name = 'is_archived'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Archived'),
            ('no', 'Not Archived'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(is_archived=True)
        elif self.value() == 'no':
            return queryset.filter(is_archived=False)
        return queryset


class PinnedStatusFilter(admin.SimpleListFilter):
    """Filter notifications by pinned status"""
    title = 'Pinned Status'
    parameter_name = 'is_pinned'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Pinned'),
            ('no', 'Not Pinned'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(is_pinned=True)
        elif self.value() == 'no':
            return queryset.filter(is_pinned=False)
        return queryset


class DeletedStatusFilter(admin.SimpleListFilter):
    """Filter notifications by deleted status"""
    title = 'Deleted Status'
    parameter_name = 'is_deleted'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Deleted'),
            ('no', 'Not Deleted'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(is_deleted=True)
        elif self.value() == 'no':
            return queryset.filter(is_deleted=False)
        return queryset


class CreatedDateFilter(admin.SimpleListFilter):
    """Filter notifications by creation date"""
    title = 'Created Date'
    parameter_name = 'created_date'
    
    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('this_week', 'This Week'),
            ('this_month', 'This Month'),
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
        )
    
    def queryset(self, request, queryset):
        today = timezone.now().date()
        
        if self.value() == 'today':
            return queryset.filter(created_at__date=today)
        elif self.value() == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        elif self.value() == 'this_week':
            start_of_week = today - timedelta(days=today.weekday())
            return queryset.filter(created_at__date__gte=start_of_week)
        elif self.value() == 'this_month':
            return queryset.filter(
                created_at__year=today.year,
                created_at__month=today.month
            )
        elif self.value() == 'last_7_days':
            return queryset.filter(
                created_at__date__gte=today - timedelta(days=7)
            )
        elif self.value() == 'last_30_days':
            return queryset.filter(
                created_at__date__gte=today - timedelta(days=30)
            )
        return queryset


# @admin.register(Notification)
# class NotificationAdmin(admin.ModelAdmin):
#     """Admin configuration for Notification model"""
    
#     list_display = (
#         'id_short',
#         'user_link',
#         'title_short',
#         'notification_type_display',
#         'priority_display',
#         'channel_display',
#         'status_display',
#         'is_read_display',
#         'is_delivered_display',
#         'created_at_formatted',
#         'actions',
#     )
    
#     list_filter = (
#         NotificationStatusFilter,
#         NotificationTypeFilter,
#         NotificationPriorityFilter,
#         NotificationChannelFilter,
#         ReadStatusFilter,
#         DeliveryStatusFilter,
#         ArchivedStatusFilter,
#         PinnedStatusFilter,
#         DeletedStatusFilter,
#         CreatedDateFilter,
#     )
    
#     search_fields = (
#         'title',
#         'message',
#         'user__username',
#         'user__email',
#         'notification_type',
#         'id',
#     )
    
#     readonly_fields = (
#         'id',
#         'created_at',
#         'updated_at',
#         'sent_at',
#         'delivered_at',
#         'read_at',
#         'archived_at',
#         'deleted_at',
#         'click_count',
#         'view_count',
#         'impression_count',
#         'delivery_attempts',
#         'last_delivery_attempt',
#         'engagement_score',
#         'open_rate',
#         'click_through_rate',
#         'conversion_rate',
#         'cost',
#     )
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': (
#                 'id',
#                 'user',
#                 'title',
#                 'message',
#                 'notification_type',
#                 'priority',
#                 'channel',
#                 'status',
#             )
#         }),
#         ('Status Information', {
#             'fields': (
#                 'is_read',
#                 'is_delivered',
#                 'is_sent',
#                 'is_archived',
#                 'is_pinned',
#                 'is_deleted',
#             )
#         }),
#         ('Timestamps', {
#             'fields': (
#                 'created_at',
#                 'updated_at',
#                 'scheduled_for',
#                 'sent_at',
#                 'delivered_at',
#                 'read_at',
#                 'archived_at',
#                 'deleted_at',
#                 'expire_date',
#             )
#         }),
#         ('Content and Actions', {
#             'fields': (
#                 'image_url',
#                 'icon_url',
#                 'thumbnail_url',
#                 'action_url',
#                 'action_text',
#                 'deep_link',
#             )
#         }),
#         ('Device and Platform', {
#             'fields': (
#                 'device_type',
#                 'platform',
#                 'language',
#             )
#         }),
#         ('Analytics', {
#             'fields': (
#                 'click_count',
#                 'view_count',
#                 'impression_count',
#                 'engagement_score',
#                 'open_rate',
#                 'click_through_rate',
#                 'conversion_rate',
#             )
#         }),
#         ('Delivery Information', {
#             'fields': (
#                 'delivery_attempts',
#                 'last_delivery_attempt',
#                 'delivery_error',
#                 'max_retries',
#                 'retry_interval',
#             )
#         }),
#         ('Cost Information', {
#             'fields': (
#                 'cost',
#                 'cost_currency',
#             )
#         }),
#         ('Relationships', {
#             'fields': (
#                 'parent_notification',
#                 'group_id',
#                 'batch_id',
#                 'campaign_id',
#                 'campaign_name',
#             )
#         }),
#         ('Metadata', {
#             'fields': (
#                 'metadata',
#                 'tags',
#                 'rich_content',
#                 'custom_style',
#                 'custom_fields',
#             )
#         }),
#         ('Settings', {
#             'fields': (
#                 'auto_delete_after_read',
#                 'auto_delete_after_days',
#                 'sound_enabled',
#                 'sound_name',
#                 'vibration_enabled',
#                 'vibration_pattern',
#                 'led_color',
#                 'led_blink_pattern',
#                 'badge_count',
#                 'position',
#                 'animation',
#                 'is_dismissible',
#                 'auto_dismiss_after',
#                 'show_progress',
#                 'progress_value',
#                 'feedback_enabled',
#                 'feedback_options',
#             )
#         }),
#         ('Security', {
#             'fields': (
#                 'is_encrypted',
#                 'encryption_key',
#             )
#         }),
#         ('Audit', {
#             'fields': (
#                 'created_by',
#                 'modified_by',
#                 'deleted_by',
#                 'version',
#                 'previous_version',
#                 'archive_reason',
#             )
#         }),
#     )
    
#     actions = [
#         'mark_as_read',
#         'mark_as_unread',
#         'mark_as_sent',
#         'mark_as_delivered',
#         'mark_as_failed',
#         'archive_selected',
#         'unarchive_selected',
#         'pin_selected',
#         'unpin_selected',
#         'soft_delete_selected',
#         'restore_selected',
#         'retry_delivery',
#         'clone_selected',
#     ]
    
#     def id_short(self, obj):
#         """Display short ID"""
#         return str(obj.id)[:8]
#     id_short.short_description = 'ID'
    
#     def user_link(self, obj):
#         """Display user as link"""
#         url = reverse('admin:auth_user_change', args=[obj.user.id])
#         return format_html('<a href="{}">{}</a>', url, obj.user.username)
#     user_link.short_description = 'User'
    
#     def title_short(self, obj):
#         """Display shortened title"""
#         if len(obj.title) > 50:
#             return obj.title[:47] + '...'
#         return obj.title
#     title_short.short_description = 'Title'
    
#     def notification_type_display(self, obj):
#         """Display notification type with badge"""
#         color_map = {
#             'payment_success': 'green',
#             'payment_failed': 'red',
#             'withdrawal_success': 'green',
#             'withdrawal_failed': 'red',
#             'task_completed': 'blue',
#             'task_assigned': 'orange',
#             'referral_signup': 'purple',
#             'security_alert': 'red',
#             'login_new_device': 'orange',
#             'kyc_approved': 'green',
#             'level_up': 'blue',
#             'achievement_unlocked': 'purple',
#             'bonus_added': 'green',
#             'wallet_credited': 'green',
#         }
#         color = color_map.get(obj.notification_type, 'gray')
#         return format_html(
#             '<span class="badge" style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px;">{}</span>',
#             color, obj.get_notification_type_display()
#         )
#     notification_type_display.short_description = 'Type'
    
#     def priority_display(self, obj):
#         """Display priority with color"""
#         color_map = {
#             'lowest': 'gray',
#             'low': 'lightblue',
#             'medium': 'blue',
#             'high': 'orange',
#             'urgent': 'red',
#             'critical': 'darkred',
#         }
#         color = color_map.get(obj.priority, 'gray')
#         return format_html(
#             '<span class="badge" style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px;">{}</span>',
#             color, obj.get_priority_display()
#         )
#     priority_display.short_description = 'Priority'
    
#     def channel_display(self, obj):
#         """Display channel"""
#         return obj.get_channel_display()
    
#     def status_display(self, obj):
#         """Display status with color"""
#         color_map = {
#             'draft': 'gray',
#             'scheduled': 'lightblue',
#             'pending': 'orange',
#             'sending': 'blue',
#             'sent': 'green',
#             'delivered': 'darkgreen',
#             'read': 'purple',
#             'failed': 'red',
#             'cancelled': 'gray',
#             'expired': 'darkgray',
#         }
#         color = color_map.get(obj.status, 'gray')
#         return format_html(
#             '<span class="badge" style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px;">{}</span>',
#             color, obj.get_status_display()
#         )
#     status_display.short_description = 'Status'
    
#     def is_read_display(self, obj):
#         """Display read status with icon"""
#         if obj.is_read:
#             return format_html(
#                 '<span style="color: green;">✓ Read</span>'
#             )
#         return format_html(
#             '<span style="color: orange;">✗ Unread</span>'
#         )
#     is_read_display.short_description = 'Read'
    
#     def is_delivered_display(self, obj):
#         """Display delivered status with icon"""
#         if obj.is_delivered:
#             return format_html(
#                 '<span style="color: green;">✓ Delivered</span>'
#             )
#         return format_html(
#             '<span style="color: orange;">✗ Not Delivered</span>'
#         )
#     is_delivered_display.short_description = 'Delivered'
    
#     def created_at_formatted(self, obj):
#         """Format created date"""
#         return obj.created_at.strftime('%Y-%m-%d %H:%M')
#     created_at_formatted.short_description = 'Created'
    
#     def actions(self, obj):
#         """Display action buttons"""
#         buttons = []
        
#         # View button
#         view_url = reverse('admin:notifications_notification_change', args=[obj.id])
#         buttons.append(
#             f'<a href="{view_url}" class="button" title="View">👁️</a>'
#         )
        
#         # Read/Unread button
#         if not obj.is_read:
#             read_url = reverse('admin:notification-mark-read', args=[obj.id])
#             buttons.append(
#                 f'<a href="{read_url}" class="button" title="Mark as Read">📖</a>'
#             )
#         else:
#             unread_url = reverse('admin:notification-mark-unread', args=[obj.id])
#             buttons.append(
#                 f'<a href="{unread_url}" class="button" title="Mark as Unread">📕</a>'
#             )
        
#         # Retry button (for failed notifications)
#         if obj.status == 'failed' and obj.delivery_attempts < obj.max_retries:
#             retry_url = reverse('admin:notification-retry', args=[obj.id])
#             buttons.append(
#                 f'<a href="{retry_url}" class="button" title="Retry Delivery">[LOADING]</a>'
#             )
        
#         # Archive/Unarchive button
#         if not obj.is_archived:
#             archive_url = reverse('admin:notification-archive', args=[obj.id])
#             buttons.append(
#                 f'<a href="{archive_url}" class="button" title="Archive">📁</a>'
#             )
#         else:
#             unarchive_url = reverse('admin:notification-unarchive', args=[obj.id])
#             buttons.append(
#                 f'<a href="{unarchive_url}" class="button" title="Unarchive">📂</a>'
#             )
        
#         return format_html(' '.join(buttons))
#     actions.short_description = 'Actions'
    
#     # Admin actions
#     def mark_as_read(self, request, queryset):
#         """Mark selected notifications as read"""
#         count = queryset.filter(is_read=False).update(
#             is_read=True,
#             read_at=timezone.now(),
#             status='read'
#         )
#         self.message_user(request, f'{count} notifications marked as read.')
#     mark_as_read.short_description = 'Mark selected as read'
    
#     def mark_as_unread(self, request, queryset):
#         """Mark selected notifications as unread"""
#         count = queryset.filter(is_read=True).update(
#             is_read=False,
#             read_at=None,
#             status='delivered'
#         )
#         self.message_user(request, f'{count} notifications marked as unread.')
#     mark_as_unread.short_description = 'Mark selected as unread'
    
#     def mark_as_sent(self, request, queryset):
#         """Mark selected notifications as sent"""
#         count = queryset.filter(is_sent=False).update(
#             is_sent=True,
#             sent_at=timezone.now(),
#             status='sent'
#         )
#         self.message_user(request, f'{count} notifications marked as sent.')
#     mark_as_sent.short_description = 'Mark selected as sent'
    
#     def mark_as_delivered(self, request, queryset):
#         """Mark selected notifications as delivered"""
#         count = queryset.filter(is_delivered=False).update(
#             is_delivered=True,
#             delivered_at=timezone.now(),
#             status='delivered'
#         )
#         self.message_user(request, f'{count} notifications marked as delivered.')
#     mark_as_delivered.short_description = 'Mark selected as delivered'
    
#     def mark_as_failed(self, request, queryset):
#         """Mark selected notifications as failed"""
#         count = queryset.update(
#             status='failed',
#             delivery_error='Manually marked as failed by admin'
#         )
#         self.message_user(request, f'{count} notifications marked as failed.')
#     mark_as_failed.short_description = 'Mark selected as failed'
    
#     def archive_selected(self, request, queryset):
#         """Archive selected notifications"""
#         count = queryset.filter(is_archived=False).update(
#             is_archived=True,
#             archived_at=timezone.now()
#         )
#         self.message_user(request, f'{count} notifications archived.')
#     archive_selected.short_description = 'Archive selected'
    
#     def unarchive_selected(self, request, queryset):
#         """Unarchive selected notifications"""
#         count = queryset.filter(is_archived=True).update(
#             is_archived=False,
#             archived_at=None
#         )
#         self.message_user(request, f'{count} notifications unarchived.')
#     unarchive_selected.short_description = 'Unarchive selected'
    
#     def pin_selected(self, request, queryset):
#         """Pin selected notifications"""
#         count = queryset.filter(is_pinned=False).update(is_pinned=True)
#         self.message_user(request, f'{count} notifications pinned.')
#     pin_selected.short_description = 'Pin selected'
    
#     def unpin_selected(self, request, queryset):
#         """Unpin selected notifications"""
#         count = queryset.filter(is_pinned=True).update(is_pinned=False)
#         self.message_user(request, f'{count} notifications unpinned.')
#     unpin_selected.short_description = 'Unpin selected'
    
#     def soft_delete_selected(self, request, queryset):
#         """Soft delete selected notifications"""
#         count = queryset.filter(is_deleted=False).update(
#             is_deleted=True,
#             deleted_at=timezone.now(),
#             deleted_by=request.user
#         )
#         self.message_user(request, f'{count} notifications soft deleted.')
#     soft_delete_selected.short_description = 'Soft delete selected'
    
#     def restore_selected(self, request, queryset):
#         """Restore soft deleted notifications"""
#         count = queryset.filter(is_deleted=True).update(
#             is_deleted=False,
#             deleted_at=None,
#             deleted_by=None
#         )
#         self.message_user(request, f'{count} notifications restored.')
#     restore_selected.short_description = 'Restore selected'
    
#     def retry_delivery(self, request, queryset):
#         """Retry delivery for selected notifications"""
#         count = 0
#         for notification in queryset:
#             if notification.can_retry_delivery():
#                 notification.prepare_for_retry()
#                 notification.save()
#                 count += 1
        
#         self.message_user(request, f'Delivery retry initiated for {count} notifications.')
#     retry_delivery.short_description = 'Retry delivery'
    
#     def clone_selected(self, request, queryset):
#         """Clone selected notifications"""
#         count = 0
#         for notification in queryset:
#             notification.clone()
#             count += 1
        
#         self.message_user(request, f'{count} notifications cloned.')
#     clone_selected.short_description = 'Clone selected'
    
#     class Media:
#         css = {
#             'all': ('admin/css/notifications.css',)
#         }
#         js = ('admin/js/notifications.js',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin configuration for Notification model"""
    
    list_display = (
        'id_short',
        'user_link',
        'title_short',
        # 'notification_type_display',
        # 'priority_display',
        # 'channel_display',
        # 'status_display',
        # 'is_read_display',
        # 'is_delivered_display',
        # 'created_at_formatted',
        'actions',
    )
    
    list_filter = (
        NotificationStatusFilter,
        NotificationTypeFilter,
        NotificationPriorityFilter,
        NotificationChannelFilter,
        ReadStatusFilter,
        DeliveryStatusFilter,
        ArchivedStatusFilter,
        PinnedStatusFilter,
        DeletedStatusFilter,
        CreatedDateFilter,
    )
    
    search_fields = (
        'title',
        'message',
        'user__username',
        'user__email',
        'notification_type',
        'id',
    )
    
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'sent_at',
        'delivered_at',
        'read_at',
        'archived_at',
        'deleted_at',
        'click_count',
        'view_count',
        'impression_count',
        'delivery_attempts',
        'last_delivery_attempt',
        'engagement_score',
        'open_rate',
        'click_through_rate',
        'conversion_rate',
        'cost',
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id',
                'user',
                'title',
                'message',
                'notification_type',
                'priority',
                'channel',
                'status',
            )
        }),
        # ... other fieldsets remain same
    )
    
    # FIXED: Use string names only, not method references
    actions = [
        'mark_as_read_action',
        'mark_as_unread_action',
        'mark_as_sent_action',
        'mark_as_delivered_action',
        'mark_as_failed_action',
        'archive_selected_action',
        'unarchive_selected_action',
        'pin_selected_action',
        'unpin_selected_action',
        'soft_delete_selected_action',
        'restore_selected_action',
        'retry_delivery_action',
        'clone_selected_action',
    ]
    
    def id_short(self, obj):
        """Display short ID"""
        return str(obj.id)[:8]
    id_short.short_description = 'ID'
    
    def user_link(self, obj):
        """Display user as link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def title_short(self, obj):
        """Display shortened title"""
        if len(obj.title) > 50:
            return obj.title[:47] + '...'
        return obj.title
    title_short.short_description = 'Title'
    
    # ... other display methods remain same ...
    
    # FIXED: Rename methods to match action names
    def mark_as_read_action(self, request, queryset):
        """Mark selected notifications as read"""
        count = queryset.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
            status='read'
        )
        self.message_user(request, f'{count} notifications marked as read.')
    mark_as_read_action.short_description = 'Mark selected as read'
    
    def mark_as_unread_action(self, request, queryset):
        """Mark selected notifications as unread"""
        count = queryset.filter(is_read=True).update(
            is_read=False,
            read_at=None,
            status='delivered'
        )
        self.message_user(request, f'{count} notifications marked as unread.')
    mark_as_unread_action.short_description = 'Mark selected as unread'
    
    def mark_as_sent_action(self, request, queryset):
        """Mark selected notifications as sent"""
        count = queryset.filter(is_sent=False).update(
            is_sent=True,
            sent_at=timezone.now(),
            status='sent'
        )
        self.message_user(request, f'{count} notifications marked as sent.')
    mark_as_sent_action.short_description = 'Mark selected as sent'
    
    def mark_as_delivered_action(self, request, queryset):
        """Mark selected notifications as delivered"""
        count = queryset.filter(is_delivered=False).update(
            is_delivered=True,
            delivered_at=timezone.now(),
            status='delivered'
        )
        self.message_user(request, f'{count} notifications marked as delivered.')
    mark_as_delivered_action.short_description = 'Mark selected as delivered'
    
    def mark_as_failed_action(self, request, queryset):
        """Mark selected notifications as failed"""
        count = queryset.update(
            status='failed',
            delivery_error='Manually marked as failed by admin'
        )
        self.message_user(request, f'{count} notifications marked as failed.')
    mark_as_failed_action.short_description = 'Mark selected as failed'
    
    def archive_selected_action(self, request, queryset):
        """Archive selected notifications"""
        count = queryset.filter(is_archived=False).update(
            is_archived=True,
            archived_at=timezone.now()
        )
        self.message_user(request, f'{count} notifications archived.')
    archive_selected_action.short_description = 'Archive selected'
    
    def unarchive_selected_action(self, request, queryset):
        """Unarchive selected notifications"""
        count = queryset.filter(is_archived=True).update(
            is_archived=False,
            archived_at=None
        )
        self.message_user(request, f'{count} notifications unarchived.')
    unarchive_selected_action.short_description = 'Unarchive selected'
    
    def pin_selected_action(self, request, queryset):
        """Pin selected notifications"""
        count = queryset.filter(is_pinned=False).update(is_pinned=True)
        self.message_user(request, f'{count} notifications pinned.')
    pin_selected_action.short_description = 'Pin selected'
    
    def unpin_selected_action(self, request, queryset):
        """Unpin selected notifications"""
        count = queryset.filter(is_pinned=True).update(is_pinned=False)
        self.message_user(request, f'{count} notifications unpinned.')
    unpin_selected_action.short_description = 'Unpin selected'
    
    def soft_delete_selected_action(self, request, queryset):
        """Soft delete selected notifications"""
        count = queryset.filter(is_deleted=False).update(
            is_deleted=True,
            deleted_at=timezone.now(),
            deleted_by=request.user
        )
        self.message_user(request, f'{count} notifications soft deleted.')
    soft_delete_selected_action.short_description = 'Soft delete selected'
    
    def restore_selected_action(self, request, queryset):
        """Restore soft deleted notifications"""
        count = queryset.filter(is_deleted=True).update(
            is_deleted=False,
            deleted_at=None,
            deleted_by=None
        )
        self.message_user(request, f'{count} notifications restored.')
    restore_selected_action.short_description = 'Restore selected'
    
    def retry_delivery_action(self, request, queryset):
        """Retry delivery for selected notifications"""
        count = 0
        for notification in queryset:
            if notification.can_retry_delivery():
                notification.prepare_for_retry()
                notification.save()
                count += 1
        
        self.message_user(request, f'Delivery retry initiated for {count} notifications.')
    retry_delivery_action.short_description = 'Retry delivery'
    
    def clone_selected_action(self, request, queryset):
        """Clone selected notifications"""
        count = 0
        for notification in queryset:
            notification.clone()
            count += 1
        
        self.message_user(request, f'{count} notifications cloned.')
    clone_selected_action.short_description = 'Clone selected'
    
    class Media:
        css = {
            'all': ('admin/css/notifications.css',)
        }
        js = ('admin/js/notifications.js',)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationTemplate model"""
    
    list_display = (
        'name',
        'template_type_display',
        'category_display',
        'is_active_display',
        'is_public_display',
        'usage_count',
        'last_used_formatted',
        'created_at_formatted',
    )
    
    list_filter = (
        'template_type',
        'category',
        'is_active',
        'is_public',
    )
    
    search_fields = (
        'name',
        'description',
        'title_en',
        'title_bn',
        'message_en',
        'message_bn',
    )
    
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'last_used',
        'usage_count',
        'version',
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name',
                'description',
                'template_type',
                'category',
                'is_active',
                'is_public',
            )
        }),
        ('Content (English)', {
            'fields': (
                'title_en',
                'message_en',
                'action_text_en',
            )
        }),
        ('Content (Bengali)', {
            'fields': (
                'title_bn',
                'message_bn',
                'action_text_bn',
            )
        }),
        ('Defaults', {
            'fields': (
                'default_priority',
                'default_channel',
                'default_language',
            )
        }),
        ('Visual Elements', {
            'fields': (
                'icon_url',
                'image_url',
            )
        }),
        ('Action Templates', {
            'fields': (
                'action_url_template',
                'deep_link_template',
            )
        }),
        ('Templates and Variables', {
            'fields': (
                'variables',
                'sample_data',
                'metadata_template',
            )
        }),
        ('Access Control', {
            'fields': (
                'allowed_groups',
                'allowed_roles',
            )
        }),
        ('Tags', {
            'fields': ('tags',)
        }),
        ('Usage Tracking', {
            'fields': (
                'usage_count',
                'last_used',
            )
        }),
        ('Versioning', {
            'fields': (
                'version',
                'parent_template',
            )
        }),
        ('Audit', {
            'fields': (
                'created_by',
                'created_at',
                'updated_by',
                'updated_at',
            )
        }),
    )
    
    actions = [
        'activate_selected',
        'deactivate_selected',
        'make_public',
        'make_private',
        'clone_selected',
        'reset_usage_count',
    ]
    
    def template_type_display(self, obj):
        """Display template type"""
        return obj.get_template_type_display()
    template_type_display.short_description = 'Type'
    
    def category_display(self, obj):
        """Display category with badge"""
        color_map = {
            'system': 'gray',
            'financial': 'green',
            'task': 'blue',
            'security': 'red',
            'marketing': 'purple',
            'social': 'orange',
            'support': 'teal',
            'achievement': 'gold',
            'gamification': 'pink',
            'admin': 'darkblue',
        }
        color = color_map.get(obj.category, 'gray')
        return format_html(
            '<span class="badge" style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px;">{}</span>',
            color, obj.get_category_display()
        )
    category_display.short_description = 'Category'
    
    def is_active_display(self, obj):
        """Display active status"""
        if obj.is_active:
            return format_html(
                '<span style="color: green;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Inactive</span>'
        )
    is_active_display.short_description = 'Active'
    
    def is_public_display(self, obj):
        """Display public status"""
        if obj.is_public:
            return format_html(
                '<span style="color: green;">✓ Public</span>'
            )
        return format_html(
            '<span style="color: blue;">✗ Private</span>'
        )
    is_public_display.short_description = 'Public'
    
    def last_used_formatted(self, obj):
        """Format last used date"""
        if obj.last_used:
            return obj.last_used.strftime('%Y-%m-%d %H:%M')
        return 'Never'
    last_used_formatted.short_description = 'Last Used'
    
    def created_at_formatted(self, obj):
        """Format created date"""
        return obj.created_at.strftime('%Y-%m-%d')
    created_at_formatted.short_description = 'Created'
    
    def activate_selected(self, request, queryset):
        """Activate selected templates"""
        count = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f'{count} templates activated.')
    activate_selected.short_description = 'Activate selected'
    
    def deactivate_selected(self, request, queryset):
        """Deactivate selected templates"""
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'{count} templates deactivated.')
    deactivate_selected.short_description = 'Deactivate selected'
    
    def make_public(self, request, queryset):
        """Make selected templates public"""
        count = queryset.filter(is_public=False).update(is_public=True)
        self.message_user(request, f'{count} templates made public.')
    make_public.short_description = 'Make public'
    
    def make_private(self, request, queryset):
        """Make selected templates private"""
        count = queryset.filter(is_public=True).update(is_public=False)
        self.message_user(request, f'{count} templates made private.')
    make_private.short_description = 'Make private'
    
    def clone_selected(self, request, queryset):
        """Clone selected templates"""
        count = 0
        for template in queryset:
            template.clone()
            count += 1
        
        self.message_user(request, f'{count} templates cloned.')
    clone_selected.short_description = 'Clone selected'
    
    def reset_usage_count(self, request, queryset):
        """Reset usage count for selected templates"""
        count = queryset.update(usage_count=0, last_used=None)
        self.message_user(request, f'Usage count reset for {count} templates.')
    reset_usage_count.short_description = 'Reset usage count'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationPreference model"""
    
    list_display = (
        'user_link',
        'enable_in_app_display',
        'enable_push_display',
        'enable_email_display',
        'enable_sms_display',
        'total_notifications_received',
        'total_notifications_read',
        'read_rate',
        'updated_at_formatted',
    )
    
    list_filter = (
        'enable_in_app',
        'enable_push',
        'enable_email',
        'enable_sms',
        'enable_telegram',
        'enable_whatsapp',
        'enable_browser',
        'do_not_disturb',
        'quiet_hours_enabled',
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
    )
    
    readonly_fields = (
        'total_notifications_received',
        'total_notifications_read',
        'total_notifications_clicked',
        'average_open_time',
        'average_click_time',
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Channel Preferences', {
            'fields': (
                'enable_in_app',
                'enable_push',
                'enable_email',
                'enable_sms',
                'enable_telegram',
                'enable_whatsapp',
                'enable_browser',
            )
        }),
        ('Type Preferences', {
            'fields': (
                'enable_system_notifications',
                'enable_financial_notifications',
                'enable_task_notifications',
                'enable_security_notifications',
                'enable_marketing_notifications',
                'enable_social_notifications',
                'enable_support_notifications',
                'enable_achievement_notifications',
                'enable_gamification_notifications',
            )
        }),
        ('Priority Preferences', {
            'fields': (
                'enable_lowest_priority',
                'enable_low_priority',
                'enable_medium_priority',
                'enable_high_priority',
                'enable_urgent_priority',
                'enable_critical_priority',
            )
        }),
        ('Notification Settings', {
            'fields': (
                'sound_enabled',
                'vibration_enabled',
                'led_enabled',
                'badge_enabled',
            )
        }),
        ('Quiet Hours', {
            'fields': (
                'quiet_hours_enabled',
                'quiet_hours_start',
                'quiet_hours_end',
            )
        }),
        ('Do Not Disturb', {
            'fields': (
                'do_not_disturb',
                'do_not_disturb_until',
            )
        }),
        ('Language and Delivery', {
            'fields': (
                'preferred_language',
                'prefer_in_app',
                'group_notifications',
                'show_previews',
            )
        }),
        ('Auto-cleanup', {
            'fields': (
                'auto_delete_read',
                'auto_delete_after_days',
            )
        }),
        ('Notification Limits', {
            'fields': (
                'max_notifications_per_day',
                'max_push_per_day',
                'max_email_per_day',
                'max_sms_per_day',
            )
        }),
        ('Analytics', {
            'fields': (
                'total_notifications_received',
                'total_notifications_read',
                'total_notifications_clicked',
                'average_open_time',
                'average_click_time',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )
    
    def user_link(self, obj):
        """Display user as link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def enable_in_app_display(self, obj):
        """Display in-app notification status"""
        if obj.enable_in_app:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    enable_in_app_display.short_description = 'In-App'
    
    def enable_push_display(self, obj):
        """Display push notification status"""
        if obj.enable_push:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    enable_push_display.short_description = 'Push'
    
    def enable_email_display(self, obj):
        """Display email notification status"""
        if obj.enable_email:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    enable_email_display.short_description = 'Email'
    
    def enable_sms_display(self, obj):
        """Display SMS notification status"""
        if obj.enable_sms:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    enable_sms_display.short_description = 'SMS'
    
    def read_rate(self, obj):
        """Calculate read rate"""
        if obj.total_notifications_received > 0:
            rate = (obj.total_notifications_read / obj.total_notifications_received) * 100
            return f'{rate:.1f}%'
        return '0%'
    read_rate.short_description = 'Read Rate'
    
    def updated_at_formatted(self, obj):
        """Format updated date"""
        return obj.updated_at.strftime('%Y-%m-%d %H:%M')
    updated_at_formatted.short_description = 'Updated'


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    """Admin configuration for DeviceToken model"""
    
    list_display = (
        'user_link',
        'device_type_display',
        'platform_display',
        'device_model',
        'app_version',
        'is_active_display',
        'push_enabled_display',
        'push_sent',
        'push_delivered',
        'delivery_rate',
        'last_active_formatted',
    )
    
    list_filter = (
        'device_type',
        'platform',
        'is_active',
        'push_enabled',
        'country',
        'language',
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'token',
        'device_model',
        'device_name',
        'manufacturer',
        'fcm_token',
        'apns_token',
    )
    
    readonly_fields = (
        'push_sent',
        'push_delivered',
        'push_failed',
        'last_push_sent',
        'last_active',
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Device Information', {
            'fields': (
                'token',
                'device_type',
                'platform',
                'app_version',
                'os_version',
                'device_model',
                'device_name',
                'manufacturer',
            )
        }),
        ('Push Tokens', {
            'fields': (
                'fcm_token',
                'apns_token',
                'web_push_token',
            )
        }),
        ('Status', {
            'fields': (
                'is_active',
                'push_enabled',
                'sound_enabled',
                'vibration_enabled',
            )
        }),
        ('Location', {
            'fields': (
                'ip_address',
                'country',
                'city',
                'timezone',
                'language',
            )
        }),
        ('Statistics', {
            'fields': (
                'push_sent',
                'push_delivered',
                'push_failed',
                'last_push_sent',
            )
        }),
        ('Timestamps', {
            'fields': (
                'last_active',
                'created_at',
                'updated_at',
            )
        }),
    )
    
    actions = [
        'activate_selected',
        'deactivate_selected',
        'enable_push_selected',
        'disable_push_selected',
    ]
    
    def user_link(self, obj):
        """Display user as link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def device_type_display(self, obj):
        """Display device type"""
        return obj.get_device_type_display()
    device_type_display.short_description = 'Device'
    
    def platform_display(self, obj):
        """Display platform"""
        return obj.get_platform_display()
    platform_display.short_description = 'Platform'
    
    def is_active_display(self, obj):
        """Display active status"""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    is_active_display.short_description = 'Active'
    
    def push_enabled_display(self, obj):
        """Display push enabled status"""
        if obj.push_enabled:
            return format_html('<span style="color: green;">✓ Enabled</span>')
        return format_html('<span style="color: red;">✗ Disabled</span>')
    push_enabled_display.short_description = 'Push'
    
    def delivery_rate(self, obj):
        """Calculate delivery rate"""
        if obj.push_sent > 0:
            rate = (obj.push_delivered / obj.push_sent) * 100
            return f'{rate:.1f}%'
        return '0%'
    delivery_rate.short_description = 'Delivery Rate'
    
    def last_active_formatted(self, obj):
        """Format last active date"""
        return obj.last_active.strftime('%Y-%m-%d %H:%M')
    last_active_formatted.short_description = 'Last Active'
    
    def activate_selected(self, request, queryset):
        """Activate selected device tokens"""
        count = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f'{count} device tokens activated.')
    activate_selected.short_description = 'Activate selected'
    
    def deactivate_selected(self, request, queryset):
        """Deactivate selected device tokens"""
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'{count} device tokens deactivated.')
    deactivate_selected.short_description = 'Deactivate selected'
    
    def enable_push_selected(self, request, queryset):
        """Enable push for selected device tokens"""
        count = queryset.filter(push_enabled=False).update(push_enabled=True)
        self.message_user(request, f'Push enabled for {count} device tokens.')
    enable_push_selected.short_description = 'Enable push'
    
    def disable_push_selected(self, request, queryset):
        """Disable push for selected device tokens"""
        count = queryset.filter(push_enabled=True).update(push_enabled=False)
        self.message_user(request, f'Push disabled for {count} device tokens.')
    disable_push_selected.short_description = 'Disable push'


@admin.register(NotificationCampaign)
class NotificationCampaignAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationCampaign model"""
    
    list_display = (
        'name',
        'campaign_type_display',
        'channel_display',
        'status_display',
        'target_count',
        'total_sent',
        'delivery_rate_display',
        'open_rate_display',
        'total_cost_display',
        'progress_bar',
        'created_at_formatted',
    )
    
    list_filter = (
        'campaign_type',
        'channel',
        'status',
    )
    
    search_fields = (
        'name',
        'description',
        'title_template',
        'message_template',
    )
    
    readonly_fields = (
        'id',
        'total_sent',
        'total_delivered',
        'total_failed',
        'total_read',
        'total_clicked',
        'delivery_rate',
        'open_rate',
        'click_through_rate',
        'conversion_rate',
        'total_cost',
        'created_at',
        'updated_at',
        'started_at',
        'completed_at',
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name',
                'description',
                'campaign_type',
                'status',
            )
        }),
        ('Content', {
            'fields': (
                'title_template',
                'message_template',
            )
        }),
        ('Delivery Settings', {
            'fields': (
                'channel',
                'priority',
                'scheduled_for',
            )
        }),
        ('Target Audience', {
            'fields': (
                'target_segment',
                'target_count',
            )
        }),
        ('Progress', {
            'fields': (
                'total_sent',
                'total_delivered',
                'total_failed',
                'total_read',
                'total_clicked',
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'delivery_rate',
                'open_rate',
                'click_through_rate',
                'conversion_rate',
            )
        }),
        ('Cost Information', {
            'fields': (
                'total_cost',
                'cost_currency',
            )
        }),
        ('A/B Testing', {
            'fields': (
                'ab_test_enabled',
                'ab_test_variants',
            )
        }),
        ('Limits', {
            'fields': (
                'send_limit',
                'daily_limit',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'started_at',
                'completed_at',
            )
        }),
        ('Created By', {
            'fields': ('created_by',)
        }),
    )
    
    actions = [
        'start_campaign',
        'pause_campaign',
        'resume_campaign',
        'complete_campaign',
        'cancel_campaign',
        'update_progress',
    ]
    
    def campaign_type_display(self, obj):
        """Display campaign type"""
        return obj.get_campaign_type_display()
    campaign_type_display.short_description = 'Type'
    
    def channel_display(self, obj):
        """Display channel"""
        return obj.get_channel_display()
    channel_display.short_description = 'Channel'
    
    def status_display(self, obj):
        """Display status with color"""
        color_map = {
            'draft': 'gray',
            'scheduled': 'lightblue',
            'running': 'green',
            'paused': 'orange',
            'completed': 'blue',
            'cancelled': 'red',
            'failed': 'darkred',
        }
        color = color_map.get(obj.status, 'gray')
        return format_html(
            '<span class="badge" style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def delivery_rate_display(self, obj):
        """Display delivery rate"""
        return f'{obj.delivery_rate:.1f}%'
    delivery_rate_display.short_description = 'Delivery'
    
    def open_rate_display(self, obj):
        """Display open rate"""
        return f'{obj.open_rate:.1f}%'
    open_rate_display.short_description = 'Open'
    
    def total_cost_display(self, obj):
        """Display total cost"""
        return f'{obj.total_cost} {obj.cost_currency}'
    total_cost_display.short_description = 'Cost'
    
    def progress_bar(self, obj):
        """Display progress bar"""
        if obj.target_count > 0:
            percentage = min(100, (obj.total_sent / obj.target_count) * 100)
        else:
            percentage = 0
        
        color = 'green' if percentage >= 90 else 'orange' if percentage >= 50 else 'red'
        
        return format_html(
            '''
            <div style="width: 100px; background-color: #eee; border-radius: 3px;">
                <div style="width: {}%; height: 20px; background-color: {}; border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">
                    {}%
                </div>
            </div>
            ''',
            percentage, color, int(percentage)
        )
    progress_bar.short_description = 'Progress'
    
    def created_at_formatted(self, obj):
        """Format created date"""
        return obj.created_at.strftime('%Y-%m-%d')
    created_at_formatted.short_description = 'Created'
    
    def start_campaign(self, request, queryset):
        """Start selected campaigns"""
        count = 0
        for campaign in queryset:
            if campaign.status == 'draft':
                campaign.start()
                count += 1
        
        self.message_user(request, f'{count} campaigns started.')
    start_campaign.short_description = 'Start selected campaigns'
    
    def pause_campaign(self, request, queryset):
        """Pause selected campaigns"""
        count = 0
        for campaign in queryset:
            if campaign.status == 'running':
                campaign.pause()
                count += 1
        
        self.message_user(request, f'{count} campaigns paused.')
    pause_campaign.short_description = 'Pause selected campaigns'
    
    def resume_campaign(self, request, queryset):
        """Resume selected campaigns"""
        count = 0
        for campaign in queryset:
            if campaign.status == 'paused':
                campaign.resume()
                count += 1
        
        self.message_user(request, f'{count} campaigns resumed.')
    resume_campaign.short_description = 'Resume selected campaigns'
    
    def complete_campaign(self, request, queryset):
        """Complete selected campaigns"""
        count = 0
        for campaign in queryset:
            if campaign.status in ['running', 'paused']:
                campaign.complete()
                count += 1
        
        self.message_user(request, f'{count} campaigns completed.')
    complete_campaign.short_description = 'Complete selected campaigns'
    
    def cancel_campaign(self, request, queryset):
        """Cancel selected campaigns"""
        count = 0
        for campaign in queryset:
            if campaign.status in ['draft', 'scheduled', 'running', 'paused']:
                campaign.cancel()
                count += 1
        
        self.message_user(request, f'{count} campaigns cancelled.')
    cancel_campaign.short_description = 'Cancel selected campaigns'
    
    def update_progress(self, request, queryset):
        """Update progress for selected campaigns"""
        count = 0
        for campaign in queryset:
            campaign.update_progress()
            count += 1
        
        self.message_user(request, f'Progress updated for {count} campaigns.')
    update_progress.short_description = 'Update progress'


@admin.register(NotificationAnalytics)
class NotificationAnalyticsAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationAnalytics model"""
    
    list_display = (
        'date',
        'total_notifications',
        'delivery_rate_display',
        'open_rate_display',
        'click_through_rate_display',
        'active_users',
        'engaged_users',
        'total_cost_display',
        'created_at_formatted',
    )
    
    list_filter = (
        'date',
    )
    
    search_fields = (
        'date',
    )
    
    readonly_fields = (
        'date',
        'total_notifications',
        'total_sent',
        'total_delivered',
        'total_read',
        'total_clicked',
        'total_failed',
        'delivery_rate',
        'open_rate',
        'click_through_rate',
        'by_type',
        'by_channel',
        'by_priority',
        'active_users',
        'engaged_users',
        'average_notifications_per_user',
        'total_cost',
        'average_cost_per_notification',
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        ('Date', {
            'fields': ('date',)
        }),
        ('Counts', {
            'fields': (
                'total_notifications',
                'total_sent',
                'total_delivered',
                'total_read',
                'total_clicked',
                'total_failed',
            )
        }),
        ('Rates', {
            'fields': (
                'delivery_rate',
                'open_rate',
                'click_through_rate',
            )
        }),
        ('Breakdown by Type', {
            'fields': ('by_type',)
        }),
        ('Breakdown by Channel', {
            'fields': ('by_channel',)
        }),
        ('Breakdown by Priority', {
            'fields': ('by_priority',)
        }),
        ('User Engagement', {
            'fields': (
                'active_users',
                'engaged_users',
                'average_notifications_per_user',
            )
        }),
        ('Cost Analysis', {
            'fields': (
                'total_cost',
                'average_cost_per_notification',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )
    
    actions = [
        'generate_daily_reports',
        'export_to_csv',
    ]
    
    def delivery_rate_display(self, obj):
        """Display delivery rate"""
        return f'{obj.delivery_rate:.1f}%'
    delivery_rate_display.short_description = 'Delivery'
    
    def open_rate_display(self, obj):
        """Display open rate"""
        return f'{obj.open_rate:.1f}%'
    open_rate_display.short_description = 'Open'
    
    def click_through_rate_display(self, obj):
        """Display click-through rate"""
        return f'{obj.click_through_rate:.1f}%'
    click_through_rate_display.short_description = 'CTR'
    
    def total_cost_display(self, obj):
        """Display total cost"""
        return f'${obj.total_cost:.2f}'
    total_cost_display.short_description = 'Cost'
    
    def created_at_formatted(self, obj):
        """Format created date"""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_formatted.short_description = 'Generated'
    
    def generate_daily_reports(self, request, queryset):
        """Generate daily reports for selected dates"""
        from .models import NotificationAnalytics
        
        count = 0
        for analytics in queryset:
            NotificationAnalytics.generate_daily_report(analytics.date)
            count += 1
        
        self.message_user(request, f'Daily reports generated for {count} dates.')
    generate_daily_reports.short_description = 'Generate daily reports'
    
    def export_to_csv(self, request, queryset):
        """Export selected analytics to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="notification_analytics.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Total Notifications', 'Total Sent', 'Total Delivered',
            'Total Read', 'Total Clicked', 'Total Failed', 'Delivery Rate',
            'Open Rate', 'Click Through Rate', 'Active Users', 'Engaged Users',
            'Avg Notifications per User', 'Total Cost'
        ])
        
        for analytics in queryset:
            writer.writerow([
                analytics.date,
                analytics.total_notifications,
                analytics.total_sent,
                analytics.total_delivered,
                analytics.total_read,
                analytics.total_clicked,
                analytics.total_failed,
                analytics.delivery_rate,
                analytics.open_rate,
                analytics.click_through_rate,
                analytics.active_users,
                analytics.engaged_users,
                analytics.average_notifications_per_user,
                analytics.total_cost,
            ])
        
        return response
    export_to_csv.short_description = 'Export to CSV'


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationRule model"""
    
    list_display = (
        'name',
        'trigger_type_display',
        'action_type_display',
        'target_type_display',
        'is_active_display',
        'is_enabled_display',
        'trigger_count',
        'success_rate',
        'last_triggered_formatted',
        'created_at_formatted',
    )
    
    list_filter = (
        'trigger_type',
        'action_type',
        'target_type',
        'is_active',
        'is_enabled',
    )
    
    search_fields = (
        'name',
        'description',
    )
    
    readonly_fields = (
        'trigger_count',
        'success_count',
        'failure_count',
        'last_triggered',
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name',
                'description',
            )
        }),
        ('Trigger', {
            'fields': (
                'trigger_type',
                'trigger_config',
            )
        }),
        ('Conditions', {
            'fields': ('conditions',)
        }),
        ('Action', {
            'fields': (
                'action_type',
                'action_config',
            )
        }),
        ('Target', {
            'fields': (
                'target_type',
                'target_config',
            )
        }),
        ('Status', {
            'fields': (
                'is_active',
                'is_enabled',
            )
        }),
        ('Execution', {
            'fields': (
                'trigger_count',
                'success_count',
                'failure_count',
                'last_triggered',
            )
        }),
        ('Limits', {
            'fields': (
                'max_executions',
                'execution_interval',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
        ('Created By', {
            'fields': ('created_by',)
        }),
    )
    
    actions = [
        'activate_selected',
        'deactivate_selected',
        'enable_selected',
        'disable_selected',
        'execute_selected',
        'test_selected',
    ]
    
    def trigger_type_display(self, obj):
        """Display trigger type"""
        return obj.get_trigger_type_display()
    trigger_type_display.short_description = 'Trigger'
    
    def action_type_display(self, obj):
        """Display action type"""
        return obj.get_action_type_display()
    action_type_display.short_description = 'Action'
    
    def target_type_display(self, obj):
        """Display target type"""
        return obj.get_target_type_display()
    target_type_display.short_description = 'Target'
    
    def is_active_display(self, obj):
        """Display active status"""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    is_active_display.short_description = 'Active'
    
    def is_enabled_display(self, obj):
        """Display enabled status"""
        if obj.is_enabled:
            return format_html('<span style="color: green;">✓ Enabled</span>')
        return format_html('<span style="color: orange;">✗ Disabled</span>')
    is_enabled_display.short_description = 'Enabled'
    
    def success_rate(self, obj):
        """Calculate success rate"""
        if obj.trigger_count > 0:
            rate = (obj.success_count / obj.trigger_count) * 100
            return f'{rate:.1f}%'
        return '0%'
    success_rate.short_description = 'Success Rate'
    
    def last_triggered_formatted(self, obj):
        """Format last triggered date"""
        if obj.last_triggered:
            return obj.last_triggered.strftime('%Y-%m-%d %H:%M')
        return 'Never'
    last_triggered_formatted.short_description = 'Last Triggered'
    
    def created_at_formatted(self, obj):
        """Format created date"""
        return obj.created_at.strftime('%Y-%m-%d')
    created_at_formatted.short_description = 'Created'
    
    def activate_selected(self, request, queryset):
        """Activate selected rules"""
        count = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f'{count} rules activated.')
    activate_selected.short_description = 'Activate selected'
    
    def deactivate_selected(self, request, queryset):
        """Deactivate selected rules"""
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'{count} rules deactivated.')
    deactivate_selected.short_description = 'Deactivate selected'
    
    def enable_selected(self, request, queryset):
        """Enable selected rules"""
        count = queryset.filter(is_enabled=False).update(is_enabled=True)
        self.message_user(request, f'{count} rules enabled.')
    enable_selected.short_description = 'Enable selected'
    
    def disable_selected(self, request, queryset):
        """Disable selected rules"""
        count = queryset.filter(is_enabled=True).update(is_enabled=False)
        self.message_user(request, f'{count} rules disabled.')
    disable_selected.short_description = 'Disable selected'
    
    def execute_selected(self, request, queryset):
        """Execute selected rules"""
        count = 0
        for rule in queryset:
            if rule.can_execute():
                rule.execute()
                count += 1
        
        self.message_user(request, f'{count} rules executed.')
    execute_selected.short_description = 'Execute selected'
    
    def test_selected(self, request, queryset):
        """Test selected rules"""
        count = 0
        for rule in queryset:
            try:
                rule.test_execution()
                count += 1
            except Exception as e:
                self.message_user(request, f'Error testing rule {rule.name}: {str(e)}', level='error')
        
        self.message_user(request, f'{count} rules tested successfully.')
    test_selected.short_description = 'Test selected'


@admin.register(NotificationFeedback)
class NotificationFeedbackAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationFeedback model"""
    
    list_display = (
        'notification_link',
        'user_link',
        'rating_stars',
        'feedback_type_display',
        'is_helpful_display',
        'would_like_more_display',
        'created_at_formatted',
    )
    
    list_filter = (
        'feedback_type',
        'rating',
        'is_helpful',
        'would_like_more',
    )
    
    search_fields = (
        'notification__title',
        'user__username',
        'user__email',
        'feedback',
    )
    
    readonly_fields = (
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        ('Feedback Information', {
            'fields': (
                'notification',
                'user',
            )
        }),
        ('Feedback Details', {
            'fields': (
                'rating',
                'feedback',
                'feedback_type',
                'is_helpful',
                'would_like_more',
            )
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )
    
    def notification_link(self, obj):
        """Display notification as link"""
        url = reverse('admin:notifications_notification_change', args=[obj.notification.id])
        title_short = obj.notification.title[:50] + '...' if len(obj.notification.title) > 50 else obj.notification.title
        return format_html('<a href="{}">{}</a>', url, title_short)
    notification_link.short_description = 'Notification'
    
    def user_link(self, obj):
        """Display user as link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def rating_stars(self, obj):
        """Display rating as stars"""
        if obj.rating:
            stars = '★' * obj.rating + '☆' * (5 - obj.rating)
            return format_html(
                '<span style="color: gold; font-size: 14px;">{}</span>',
                stars
            )
        return '-'
    rating_stars.short_description = 'Rating'
    
    def feedback_type_display(self, obj):
        """Display feedback type"""
        return obj.get_feedback_type_display()
    feedback_type_display.short_description = 'Type'
    
    def is_helpful_display(self, obj):
        """Display helpful status"""
        if obj.is_helpful is None:
            return '-'
        elif obj.is_helpful:
            return format_html('<span style="color: green;">✓ Helpful</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Helpful</span>')
    is_helpful_display.short_description = 'Helpful'
    
    def would_like_more_display(self, obj):
        """Display would like more status"""
        if obj.would_like_more is None:
            return '-'
        elif obj.would_like_more:
            return format_html('<span style="color: green;">✓ Yes</span>')
        else:
            return format_html('<span style="color: red;">✗ No</span>')
    would_like_more_display.short_description = 'Want More'
    
    def created_at_formatted(self, obj):
        """Format created date"""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_formatted.short_description = 'Created'


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationLog model"""
    
    list_display = (
        'log_type_display',
        'log_level_display',
        'notification_link',
        'user_link',
        'message_short',
        'source',
        'created_at_formatted',
    )
    
    list_filter = (
        'log_type',
        'log_level',
    )
    
    search_fields = (
        'message',
        'notification__title',
        'user__username',
        'user__email',
        'source',
        'ip_address',
    )
    
    readonly_fields = (
        'id',
        'created_at',
    )
    
    fieldsets = (
        ('Log Information', {
            'fields': (
                'log_type',
                'log_level',
                'message',
                'details',
            )
        }),
        ('Source Information', {
            'fields': (
                'notification',
                'user',
                'source',
                'ip_address',
                'user_agent',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def log_type_display(self, obj):
        """Display log type with color"""
        color_map = {
            'delivery': 'green',
            'read': 'blue',
            'click': 'purple',
            'dismiss': 'orange',
            'archive': 'gray',
            'delete': 'red',
            'error': 'darkred',
            'warning': 'orange',
            'info': 'blue',
            'debug': 'gray',
        }
        color = color_map.get(obj.log_type, 'gray')
        return format_html(
            '<span class="badge" style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px;">{}</span>',
            color, obj.get_log_type_display()
        )
    log_type_display.short_description = 'Type'
    
    def log_level_display(self, obj):
        """Display log level with color"""
        color_map = {
            'debug': 'gray',
            'info': 'blue',
            'warning': 'orange',
            'error': 'red',
            'critical': 'darkred',
        }
        color = color_map.get(obj.log_level, 'gray')
        return format_html(
            '<span class="badge" style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px;">{}</span>',
            color, obj.get_log_level_display()
        )
    log_level_display.short_description = 'Level'
    
    def notification_link(self, obj):
        """Display notification as link"""
        if obj.notification:
            url = reverse('admin:notifications_notification_change', args=[obj.notification.id])
            return format_html('<a href="{}">View</a>', url)
        return '-'
    notification_link.short_description = 'Notification'
    
    def user_link(self, obj):
        """Display user as link"""
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return '-'
    user_link.short_description = 'User'
    
    def message_short(self, obj):
        """Display shortened message"""
        if len(obj.message) > 100:
            return obj.message[:97] + '...'
        return obj.message
    message_short.short_description = 'Message'
    
    def created_at_formatted(self, obj):
        """Format created date"""
        return obj.created_at.strftime('%Y-%m-%d %H:%M:%S')
    created_at_formatted.short_description = 'Created'
    
    actions = ['cleanup_old_logs']
    
    def cleanup_old_logs(self, request, queryset):
        """Cleanup old logs"""
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=90)
        count, _ = queryset.filter(created_at__lt=cutoff_date).delete()
        
        self.message_user(request, f'{count} old logs deleted.')
    cleanup_old_logs.short_description = 'Cleanup old logs (90+ days)'
    
    
    from django.contrib.admin import AdminSite
from django.urls import path

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.urls import path

# ১. কাস্টম অ্যাডমিন সাইট ক্লাস
class NotificationAdminSite(AdminSite):
    site_header = "Notification Admin"
    site_title = "Notification System Admin"
    index_title = "Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        try:
            from .admin_views import (
                notification_mark_read, notification_mark_unread,
                notification_archive, notification_unarchive,
                notification_retry, dashboard_view,
                analytics_view, reports_view, system_status_view,
            )
            
            # আপনার সব কাস্টম ইউআরএল এখানে
            my_urls = [
                path('notification/<uuid:pk>/mark-read/', self.admin_view(notification_mark_read), name='notification-mark-read'),
                path('notification/<uuid:pk>/mark-unread/', self.admin_view(notification_mark_unread), name='notification-mark-unread'),
                path('notification/<uuid:pk>/archive/', self.admin_view(notification_archive), name='notification-archive'),
                path('notification/<uuid:pk>/unarchive/', self.admin_view(notification_unarchive), name='notification-unarchive'),
                path('notification/<uuid:pk>/retry/', self.admin_view(notification_retry), name='notification-retry'),
                path('dashboard/', self.admin_view(dashboard_view), name='notification-dashboard'),
                path('analytics/', self.admin_view(analytics_view), name='notification-analytics'),
                path('reports/', self.admin_view(reports_view), name='notification-reports'),
                path('system-status/', self.admin_view(system_status_view), name='notification-system-status'),
            ]
            return my_urls + urls
        except (ImportError, ModuleNotFoundError):
            # যদি admin_views ফাইল না থাকে তবে ডিফল্ট ইউআরএল চলবে
            return urls

# ২. অ্যাডমিন সাইট অবজেক্ট তৈরি
admin_site = NotificationAdminSite(name='notification_admin')

# ৩. যদি আপনি ডিফল্ট admin.site-কেও একই ইউআরএল দিতে চান (অপশনাল)
# admin.site.get_urls = admin_site.get_urls

def _force_register_notifications():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(Notification, NotificationAdmin), (NotificationTemplate, NotificationTemplateAdmin), (NotificationPreference, NotificationPreferenceAdmin), (DeviceToken, DeviceTokenAdmin), (NotificationCampaign, NotificationCampaignAdmin), (NotificationAnalytics, NotificationAnalyticsAdmin), (NotificationRule, NotificationRuleAdmin), (NotificationFeedback, NotificationFeedbackAdmin), (NotificationLog, NotificationLogAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] notifications registered {registered} models")
    except Exception as e:
        print(f"[WARN] notifications: {e}")


# ---------------------------------------------------------------------------
# Register all new split models with Django admin
# ---------------------------------------------------------------------------
try:
    from api.notifications.admin_new_models import register_all_new_models
    register_all_new_models()
except Exception as _e:
    import traceback
    traceback.print_exc()
