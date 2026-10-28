# api/admin_panel/admin/system_settings_admin.py
"""
Django Admin for SystemSettings (CPAlead earning platform).
Full admin with all fieldsets: site info, payments, points, referral,
security, fraud, app versions, email, SMS, maintenance, analytics.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.core import SystemSettings, AdminAction, Report


# @admin.register(SystemSettings) — registered in admin.py
class SystemSettingsAdmin(admin.ModelAdmin):
    """
    Full-featured admin for the SystemSettings singleton.
    All sections organized into collapsible fieldsets.
    """
    list_display = ['site_name', 'currency_code', 'maintenance_badge',
                    'referral_badge', 'android_version', 'ios_version', 'updated_at']
    readonly_fields = ['created_at', 'updated_at', 'last_modified_by']

    fieldsets = (
        # ==================== Site Info ====================
        ('🌐 Site Information', {
            'fields': (
                'site_name', 'site_tagline', 'site_description',
                'site_logo', 'site_favicon', 'site_url',
                'contact_email', 'support_email', 'admin_email',
            ),
        }),
        ('📞 Contact & Social', {
            'fields': (
                'contact_phone', 'contact_whatsapp', 'contact_address',
                'contact_facebook', 'contact_twitter', 'contact_instagram',
                'contact_telegram', 'contact_youtube', 'contact_linkedin',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Currency & Payment ====================
        ('💰 Currency & Payment Settings', {
            'fields': (
                'currency_code', 'currency_symbol',
                'min_withdrawal_amount', 'max_withdrawal_amount',
                'withdrawal_fee_percentage', 'withdrawal_fee_fixed',
                'tax_percentage',
            ),
        }),
        ('💳 Payment Gateways', {
            'fields': (
                'enable_bkash', 'enable_nagad', 'enable_rocket',
                'enable_stripe', 'enable_paypal', 'enable_bank_transfer',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Points System ====================
        ('🎯 Points & Earning System', {
            'description': 'CPAlead-style reward system configuration.',
            'fields': (
                'point_value', 'min_points_withdrawal',
                'ad_click_points', 'video_watch_points',
                'survey_complete_points', 'task_complete_points',
            ),
        }),
        ('🎁 Bonus Points', {
            'fields': (
                'referral_bonus_points', 'daily_login_bonus',
                'welcome_bonus_points', 'first_withdrawal_bonus', 'birthday_bonus',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Referral System ====================
        ('👥 Referral System', {
            'fields': (
                'enable_referral', 'referral_levels',
                'referral_percentage_level1', 'referral_percentage_level2',
                'referral_percentage_level3', 'referral_percentage_level4',
                'referral_percentage_level5',
                'referral_expiry_days', 'min_referral_withdrawal',
            ),
        }),
        # ==================== App Versions ====================
        ('📱 Android App Settings', {
            'fields': (
                'android_version', 'android_version_code',
                'android_min_version', 'android_min_version_code',
                'android_force_update', 'android_update_message',
                'android_app_link', 'android_apk_link',
            ),
            'classes': ('collapse',),
        }),
        ('🍎 iOS App Settings', {
            'fields': (
                'ios_version', 'ios_version_code',
                'ios_min_version', 'ios_min_version_code',
                'ios_force_update', 'ios_update_message', 'ios_app_link',
            ),
            'classes': ('collapse',),
        }),
        ('🌐 Web App Settings', {
            'fields': ('web_version', 'web_force_reload'),
            'classes': ('collapse',),
        }),
        # ==================== Fraud & Security ====================
        ('🛡️ Daily Limits & Fraud Prevention', {
            'description': 'Anti-fraud settings for CPAlead-style earning limits.',
            'fields': (
                'max_daily_earning_limit', 'max_daily_withdrawal_limit',
                'max_daily_ads', 'max_daily_videos',
                'max_daily_tasks', 'max_daily_surveys',
                'suspicious_activity_threshold', 'suspicious_click_speed',
                'suspicious_device_count',
                'min_ad_watch_time', 'min_video_watch_time', 'click_delay_seconds',
            ),
        }),
        ('🚫 Auto Ban Settings', {
            'fields': (
                'auto_ban_on_vpn', 'auto_ban_on_emulator',
                'auto_ban_on_root', 'auto_ban_on_multiple_accounts',
                'block_vpn_users', 'block_proxy_users', 'block_tor_users',
                'max_accounts_per_ip', 'max_accounts_per_device',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Security & Verification ====================
        ('🔐 Security & Verification', {
            'fields': (
                'enable_2fa', 'force_2fa_for_withdrawal',
                'enable_withdrawal_pin', 'withdrawal_pin_length',
                'enable_email_verification', 'enable_phone_verification',
                'enable_identity_verification',
                'require_email_for_withdrawal', 'require_phone_for_withdrawal',
                'require_identity_for_large_withdrawal', 'large_withdrawal_threshold',
            ),
            'classes': ('collapse',),
        }),
        ('🔑 Login Security', {
            'fields': (
                'max_login_attempts', 'account_lockout_minutes',
                'session_timeout_minutes', 'enable_login_notification',
                'enable_unusual_activity_alert',
                'min_password_length', 'require_password_uppercase',
                'require_password_lowercase', 'require_password_number',
                'require_password_special', 'password_expiry_days',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Withdrawal Security ====================
        ('💸 Withdrawal Security', {
            'fields': (
                'withdrawal_review_required', 'withdrawal_auto_approve_limit',
                'withdrawal_processing_time', 'withdrawal_cooldown_hours',
                'max_pending_withdrawals', 'new_user_withdrawal_delay_days',
                'new_user_daily_limit',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Email Settings ====================
        ('📧 Email / SMTP Settings', {
            'fields': (
                'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
                'smtp_use_tls', 'smtp_use_ssl',
                'email_from_name', 'email_from_address',
                'send_welcome_email', 'send_withdrawal_email',
                'send_deposit_email', 'send_referral_email',
                'send_security_alert_email',
            ),
            'classes': ('collapse',),
        }),
        # ==================== SMS Settings ====================
        ('📱 SMS Settings', {
            'fields': (
                'enable_sms', 'sms_provider', 'sms_api_key',
                'sms_api_secret', 'sms_sender_id', 'sms_api_url',
                'send_withdrawal_sms', 'send_security_alert_sms', 'send_otp_sms',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Maintenance ====================
        ('🔧 Maintenance Mode', {
            'fields': (
                'maintenance_mode', 'maintenance_message',
                'maintenance_start', 'maintenance_end',
                'allow_admin_during_maintenance', 'maintenance_reason',
            ),
        }),
        # ==================== Performance ====================
        ('⚡ Cache & Performance', {
            'fields': (
                'cache_timeout', 'enable_caching', 'enable_query_optimization',
                'max_upload_size', 'enable_compression',
                'enable_rate_limiting', 'api_rate_limit_per_minute',
                'api_rate_limit_per_hour',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Analytics ====================
        ('📊 Analytics & Tracking', {
            'fields': (
                'enable_analytics', 'google_analytics_id',
                'facebook_pixel_id', 'google_tag_manager_id', 'hotjar_id',
                'track_user_activity', 'track_referral_source',
                'track_device_info', 'track_location',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Notifications ====================
        ('🔔 Push Notifications', {
            'fields': (
                'enable_push_notifications', 'firebase_server_key', 'firebase_sender_id',
                'notify_on_withdrawal', 'notify_on_deposit', 'notify_on_referral',
                'notify_on_bonus', 'notify_on_task_available',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Features ====================
        ('🎮 Gamification & Social', {
            'fields': (
                'enable_leaderboard', 'enable_badges', 'enable_achievements',
                'enable_daily_streak', 'enable_social_sharing',
                'enable_user_profiles', 'enable_chat', 'enable_comments',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Legal ====================
        ('⚖️ Legal & Compliance', {
            'fields': (
                'terms_url', 'privacy_policy_url', 'refund_policy_url',
                'cookie_policy_url', 'disclaimer_text', 'copyright_text',
                'enable_gdpr', 'data_retention_days', 'allow_data_export',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Debug & Logs ====================
        ('🛠️ Debug & Logging', {
            'fields': (
                'enable_debug_mode', 'enable_api_logs', 'log_retention_days',
            ),
            'classes': ('collapse',),
        }),
        # ==================== Audit ====================
        ('📋 Audit Trail', {
            'fields': ('last_modified_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='Maintenance', boolean=True)
    def maintenance_badge(self, obj):
        return obj.maintenance_mode

    @admin.display(description='Referral', boolean=True)
    def referral_badge(self, obj):
        return obj.enable_referral

    def has_add_permission(self, request):
        """Only allow one instance — prevent creating a second."""
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Do not allow deleting the singleton."""
        return False

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj:
            fields.append('created_at')
        return fields

    def updated_at(self, obj):
        if obj.updated_at:
            return obj.updated_at.strftime('%Y-%m-%d %H:%M')
        return '-'
    updated_at.short_description = 'Last Updated'


# @admin.register(AdminAction) — registered in admin.py
class AdminActionAdmin(admin.ModelAdmin):
    """Admin for AdminAction log."""
    list_display = ['admin', 'action_type', 'target_user', 'ip_address', 'created_at']
    list_filter = ['action_type']
    search_fields = ['admin__username', 'target_user__username', 'description', 'ip_address']
    readonly_fields = ['admin', 'action_type', 'target_user', 'description',
                       'metadata', 'ip_address', 'created_at', 'updated_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser