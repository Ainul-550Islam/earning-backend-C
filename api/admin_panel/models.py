from django.db import models
from core.models import TimeStampedModel
# from api.users.models import User
from django.conf import settings
from django.contrib.auth.models import User
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
import json


class AdminAction(TimeStampedModel):
    ACTION_TYPES = (
        ('user_ban', 'User Ban'),
        ('user_unban', 'User Unban'),
        ('payment_approve', 'Payment Approve'),
        ('payment_reject', 'Payment Reject'),
        ('content_delete', 'Content Delete'),
        ('setting_change', 'Setting Change'),
    )
    
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_panel_adminaction_admin')
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_panel_adminaction_target_user')
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Admin Action'
        verbose_name_plural = 'Admin Actions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.admin.username} - {self.action_type}"


class Report(TimeStampedModel):
    REPORT_TYPES = (
        ('user', 'User Report'),
        ('payment', 'Payment Report'),
        ('revenue', 'Revenue Report'),
        ('activity', 'Activity Report'),
    )
    
    title = models.CharField(max_length=255, default="New Report")
    description = models.TextField(null=True, blank=True) # অ্যাডমিনের search_fields ও fieldsets এর জন্য
    report_id = models.CharField(max_length=100, unique=True, editable=False, null=True)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    # অ্যাডমিনের 'Report Data' সেকশনের জন্য
    report_data = models.JSONField(default=dict, blank=True) 
    
    # অ্যাডমিনের 'File Information' সেকশনের জন্য
    report_file = models.FileField(upload_to='reports/', null=True, blank=True)
    file_format = models.CharField(max_length=10, blank=True, null=True)
    file_size = models.CharField(max_length=50, blank=True, null=True)
    
    status = models.CharField(max_length=20, default='pending')
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.report_type})"

    def save(self, *args, **kwargs):
        if not self.report_id:
            import uuid
            self.report_id = f"REP-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    



class SystemSettings(models.Model):
    """System-wide settings and configuration"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    
    # ==================== Site Information ====================
    site_name = models.CharField(max_length=255, default="Earning Platform")
    site_tagline = models.CharField(max_length=255, blank=True, default="Earn Money Online")
    site_description = models.TextField(blank=True)
    site_logo = models.ImageField(upload_to='site_logos/', blank=True, null=True)
    site_favicon = models.ImageField(upload_to='favicons/', blank=True, null=True)
    site_url = models.URLField(default="https://earn.example.com")
    contact_email = models.EmailField(default="support@earn.example.com")
    support_email = models.EmailField(default="help@earn.example.com")
    admin_email = models.EmailField(default="admin@earn.example.com")
    
    # ==================== Contact Information ====================
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_whatsapp = models.CharField(max_length=20, blank=True)
    contact_address = models.TextField(blank=True)
    contact_facebook = models.URLField(blank=True)
    contact_twitter = models.URLField(blank=True)
    contact_instagram = models.URLField(blank=True)
    contact_telegram = models.URLField(blank=True)
    contact_youtube = models.URLField(blank=True)
    contact_linkedin = models.URLField(blank=True)
    
    # ==================== Currency & Payment Settings ====================
    currency_code = models.CharField(max_length=3, default="BDT")
    currency_symbol = models.CharField(max_length=5, default="৳")
    min_withdrawal_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=100.00,
        help_text="Minimum amount users can withdraw"
    )
    max_withdrawal_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=10000.00,
        help_text="Maximum amount users can withdraw at once"
    )
    withdrawal_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=2.50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Withdrawal fee percentage (0-100)"
    )
    withdrawal_fee_fixed = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Fixed withdrawal fee amount"
    )
    tax_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Tax deduction percentage"
    )
    
    # Payment Gateway Settings
    enable_bkash = models.BooleanField(default=True)
    enable_nagad = models.BooleanField(default=True)
    enable_rocket = models.BooleanField(default=False)
    enable_stripe = models.BooleanField(default=False)
    enable_paypal = models.BooleanField(default=False)
    enable_bank_transfer = models.BooleanField(default=False)
    
    # ==================== Points System ====================
    point_value = models.DecimalField(
        max_digits=10, decimal_places=4, default=0.01,
        help_text="How much 1 point is worth in currency"
    )
    min_points_withdrawal = models.IntegerField(
        default=1000,
        help_text="Minimum points needed to withdraw"
    )
    
    # Bonus Points
    referral_bonus_points = models.IntegerField(default=500)
    daily_login_bonus = models.IntegerField(default=50)
    welcome_bonus_points = models.IntegerField(default=1000)
    first_withdrawal_bonus = models.IntegerField(default=200)
    birthday_bonus = models.IntegerField(default=500)
    
    # Ad Viewing Rewards
    ad_click_points = models.IntegerField(default=10, help_text="Points per ad click")
    video_watch_points = models.IntegerField(default=50, help_text="Points per video watch")
    survey_complete_points = models.IntegerField(default=100, help_text="Points per survey")
    task_complete_points = models.IntegerField(default=75, help_text="Points per task")
    
    # ==================== Referral System ====================
    enable_referral = models.BooleanField(default=True)
    referral_levels = models.IntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    
    # Level-wise referral commission
    referral_percentage_level1 = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    referral_percentage_level2 = models.DecimalField(
        max_digits=5, decimal_places=2, default=5.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    referral_percentage_level3 = models.DecimalField(
        max_digits=5, decimal_places=2, default=2.50,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    referral_percentage_level4 = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    referral_percentage_level5 = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.50,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    referral_expiry_days = models.IntegerField(
        default=365,
        help_text="Days after which referral link expires (0 = never)"
    )
    min_referral_withdrawal = models.IntegerField(
        default=5,
        help_text="Minimum referrals needed before withdrawal"
    )
    
    # ==================== App & Version Control ====================
    # Android Version Control
    android_version = models.CharField(
        max_length=20, default="1.0.0",
        help_text="Current Android app version in Play Store"
    )
    android_version_code = models.IntegerField(
        default=1,
        help_text="Android version code (integer)"
    )
    android_min_version = models.CharField(
        max_length=20, default="1.0.0",
        help_text="Minimum required Android version to use app"
    )
    android_min_version_code = models.IntegerField(
        default=1,
        help_text="Minimum version code required"
    )
    android_force_update = models.BooleanField(
        default=False,
        help_text="Force users to update Android app"
    )
    android_update_message = models.TextField(
        default="A new version is available. Please update to continue.",
        help_text="Message shown when update is required"
    )
    android_app_link = models.URLField(
        blank=True,
        help_text="Google Play Store link"
    )
    android_apk_link = models.URLField(
        blank=True,
        help_text="Direct APK download link"
    )
    
    # iOS Version Control
    ios_version = models.CharField(
        max_length=20, default="1.0.0",
        help_text="Current iOS app version in App Store"
    )
    ios_version_code = models.IntegerField(
        default=1,
        help_text="iOS version code (build number)"
    )
    ios_min_version = models.CharField(
        max_length=20, default="1.0.0",
        help_text="Minimum required iOS version"
    )
    ios_min_version_code = models.IntegerField(
        default=1,
        help_text="Minimum iOS build number required"
    )
    ios_force_update = models.BooleanField(
        default=False,
        help_text="Force users to update iOS app"
    )
    ios_update_message = models.TextField(
        default="A new version is available. Please update to continue."
    )
    ios_app_link = models.URLField(
        blank=True,
        help_text="Apple App Store link"
    )
    
    # Web Version Control
    web_version = models.CharField(max_length=20, default="1.0.0")
    web_force_reload = models.BooleanField(
        default=False,
        help_text="Force browser cache clear and reload"
    )
    
    # ==================== Fraud & Security Settings ====================
    # Daily Limits
    max_daily_earning_limit = models.DecimalField(
        max_digits=10, decimal_places=2, default=1000.00,
        help_text="Maximum amount a user can earn per day"
    )
    max_daily_withdrawal_limit = models.DecimalField(
        max_digits=10, decimal_places=2, default=5000.00,
        help_text="Maximum withdrawal amount per day"
    )
    max_daily_ads = models.IntegerField(
        default=100,
        help_text="Maximum ads a user can view per day"
    )
    max_daily_videos = models.IntegerField(
        default=50,
        help_text="Maximum videos a user can watch per day"
    )
    max_daily_tasks = models.IntegerField(
        default=20,
        help_text="Maximum tasks a user can complete per day"
    )
    max_daily_surveys = models.IntegerField(
        default=10,
        help_text="Maximum surveys a user can complete per day"
    )
    
    # Suspicious Activity Detection
    suspicious_activity_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=500.00,
        help_text="If user earns this much in an hour, flag as suspicious"
    )
    suspicious_click_speed = models.IntegerField(
        default=5,
        help_text="Number of clicks in 60 seconds to flag as bot"
    )
    suspicious_device_count = models.IntegerField(
        default=3,
        help_text="Max devices per account before flagging"
    )
    
    # Auto Ban Settings
    auto_ban_on_vpn = models.BooleanField(
        default=False,
        help_text="Automatically ban users detected using VPN"
    )
    auto_ban_on_emulator = models.BooleanField(
        default=True,
        help_text="Automatically ban users using emulators"
    )
    auto_ban_on_root = models.BooleanField(
        default=False,
        help_text="Automatically ban users with rooted devices"
    )
    auto_ban_on_multiple_accounts = models.BooleanField(
        default=True,
        help_text="Automatically ban duplicate accounts"
    )
    
    # IP & Device Restrictions
    max_accounts_per_ip = models.IntegerField(
        default=3,
        help_text="Maximum accounts allowed per IP address"
    )
    max_accounts_per_device = models.IntegerField(
        default=1,
        help_text="Maximum accounts allowed per device"
    )
    block_vpn_users = models.BooleanField(
        default=False,
        help_text="Block users detected using VPN"
    )
    block_proxy_users = models.BooleanField(
        default=False,
        help_text="Block users using proxy servers"
    )
    block_tor_users = models.BooleanField(
        default=True,
        help_text="Block users using Tor network"
    )
    
    # Click & Action Fraud Prevention
    min_ad_watch_time = models.IntegerField(
        default=30,
        help_text="Minimum seconds to watch ad (prevents quick clicks)"
    )
    min_video_watch_time = models.IntegerField(
        default=120,
        help_text="Minimum seconds to watch video"
    )
    click_delay_seconds = models.IntegerField(
        default=10,
        help_text="Minimum seconds between consecutive clicks"
    )
    
    # ==================== Security & Verification ====================
    # Account Security
    enable_2fa = models.BooleanField(
        default=False,
        help_text="Enable two-factor authentication"
    )
    force_2fa_for_withdrawal = models.BooleanField(
        default=False,
        help_text="Require 2FA for withdrawals"
    )
    enable_withdrawal_pin = models.BooleanField(
        default=True,
        help_text="Require PIN for withdrawals"
    )
    withdrawal_pin_length = models.IntegerField(
        default=4,
        validators=[MinValueValidator(4), MaxValueValidator(8)]
    )
    
    # Verification Requirements
    enable_email_verification = models.BooleanField(default=True)
    enable_phone_verification = models.BooleanField(default=True)
    enable_identity_verification = models.BooleanField(
        default=False,
        help_text="Require ID card/passport verification"
    )
    require_email_for_withdrawal = models.BooleanField(default=True)
    require_phone_for_withdrawal = models.BooleanField(default=True)
    require_identity_for_large_withdrawal = models.BooleanField(default=False)
    large_withdrawal_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=5000.00,
        help_text="Amount that triggers identity verification requirement"
    )
    
    # Login Security
    max_login_attempts = models.IntegerField(
        default=5,
        help_text="Maximum failed login attempts before lockout"
    )
    account_lockout_minutes = models.IntegerField(
        default=30,
        help_text="Minutes to lock account after max failed attempts"
    )
    session_timeout_minutes = models.IntegerField(
        default=60,
        help_text="Auto logout after inactivity (minutes)"
    )
    enable_login_notification = models.BooleanField(
        default=True,
        help_text="Send email on new login"
    )
    enable_unusual_activity_alert = models.BooleanField(
        default=True,
        help_text="Alert on suspicious login locations"
    )
    
    # Password Policy
    min_password_length = models.IntegerField(
        default=8,
        validators=[MinValueValidator(6), MaxValueValidator(32)]
    )
    require_password_uppercase = models.BooleanField(default=True)
    require_password_lowercase = models.BooleanField(default=True)
    require_password_number = models.BooleanField(default=True)
    require_password_special = models.BooleanField(default=False)
    password_expiry_days = models.IntegerField(
        default=0,
        help_text="Force password change after X days (0 = never)"
    )
    
    # ==================== Withdrawal Security ====================
    withdrawal_review_required = models.BooleanField(
        default=False,
        help_text="Admin must approve all withdrawals"
    )
    withdrawal_auto_approve_limit = models.DecimalField(
        max_digits=10, decimal_places=2, default=100.00,
        help_text="Auto-approve withdrawals below this amount"
    )
    withdrawal_processing_time = models.IntegerField(
        default=24,
        help_text="Hours to process withdrawal"
    )
    withdrawal_cooldown_hours = models.IntegerField(
        default=24,
        help_text="Hours between withdrawal requests"
    )
    max_pending_withdrawals = models.IntegerField(
        default=3,
        help_text="Maximum pending withdrawal requests"
    )
    
    # New User Restrictions
    new_user_withdrawal_delay_days = models.IntegerField(
        default=7,
        help_text="Days before new users can withdraw"
    )
    new_user_daily_limit = models.DecimalField(
        max_digits=10, decimal_places=2, default=100.00,
        help_text="Daily earning limit for new users"
    )
    
    # ==================== Email Settings ====================
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    email_from_name = models.CharField(max_length=255, default="Earning Platform")
    email_from_address = models.EmailField(blank=True)
    
    # Email Notifications
    send_welcome_email = models.BooleanField(default=True)
    send_withdrawal_email = models.BooleanField(default=True)
    send_deposit_email = models.BooleanField(default=True)
    send_referral_email = models.BooleanField(default=True)
    send_security_alert_email = models.BooleanField(default=True)
    
    # ==================== SMS Settings ====================
    enable_sms = models.BooleanField(default=False)
    sms_provider = models.CharField(
        max_length=50, blank=True,
        choices=[
            ('twilio', 'Twilio'),
            ('nexmo', 'Nexmo'),
            ('msg91', 'MSG91'),
            ('bulksms', 'BulkSMS'),
            ('custom', 'Custom'),
        ]
    )
    sms_api_key = models.CharField(max_length=255, blank=True)
    sms_api_secret = models.CharField(max_length=255, blank=True)
    sms_sender_id = models.CharField(max_length=20, blank=True)
    sms_api_url = models.URLField(blank=True)
    
    # SMS Notifications
    send_withdrawal_sms = models.BooleanField(default=False)
    send_security_alert_sms = models.BooleanField(default=False)
    send_otp_sms = models.BooleanField(default=True)
    
    # ==================== Maintenance Mode ====================
    maintenance_mode = models.BooleanField(
        default=False,
        help_text="Enable maintenance mode (blocks all users except admins)"
    )
    maintenance_message = models.TextField(
        default="We're currently performing maintenance. Please check back soon.",
        help_text="Message shown to users during maintenance"
    )
    maintenance_start = models.DateTimeField(blank=True, null=True)
    maintenance_end = models.DateTimeField(blank=True, null=True)
    allow_admin_during_maintenance = models.BooleanField(
        default=True,
        help_text="Allow admin users during maintenance"
    )
    maintenance_reason = models.CharField(
        max_length=255, blank=True,
        help_text="Internal reason for maintenance"
    )
    
    # ==================== Cache & Performance ====================
    cache_timeout = models.IntegerField(
        default=300,
        help_text="Cache timeout in seconds (default 5 minutes)"
    )
    enable_caching = models.BooleanField(default=True)
    enable_query_optimization = models.BooleanField(default=True)
    max_upload_size = models.IntegerField(
        default=5242880,
        help_text="Maximum upload size in bytes (default 5MB)"
    )
    enable_compression = models.BooleanField(
        default=True,
        help_text="Enable gzip compression"
    )
    
    # Rate Limiting
    enable_rate_limiting = models.BooleanField(default=True)
    api_rate_limit_per_minute = models.IntegerField(
        default=60,
        help_text="API requests allowed per minute per user"
    )
    api_rate_limit_per_hour = models.IntegerField(
        default=1000,
        help_text="API requests allowed per hour per user"
    )
    
    # ==================== Analytics & Tracking ====================
    enable_analytics = models.BooleanField(default=True)
    google_analytics_id = models.CharField(max_length=50, blank=True)
    facebook_pixel_id = models.CharField(max_length=50, blank=True)
    google_tag_manager_id = models.CharField(max_length=50, blank=True)
    hotjar_id = models.CharField(max_length=50, blank=True)
    
    # User Tracking
    track_user_activity = models.BooleanField(
        default=True,
        help_text="Track user actions for analytics"
    )
    track_referral_source = models.BooleanField(default=True)
    track_device_info = models.BooleanField(default=True)
    track_location = models.BooleanField(default=True)
    
    # ==================== Legal & Compliance ====================
    terms_url = models.URLField(blank=True)
    privacy_policy_url = models.URLField(blank=True)
    refund_policy_url = models.URLField(blank=True)
    cookie_policy_url = models.URLField(blank=True)
    disclaimer_text = models.TextField(blank=True)
    copyright_text = models.CharField(
        max_length=255,
        default="© 2024 Earning Platform. All rights reserved."
    )
    
    # GDPR Compliance
    enable_gdpr = models.BooleanField(
        default=False,
        help_text="Enable GDPR compliance features"
    )
    data_retention_days = models.IntegerField(
        default=365,
        help_text="Days to retain user data after account deletion"
    )
    allow_data_export = models.BooleanField(
        default=True,
        help_text="Allow users to export their data"
    )
    
    # ==================== Notification Settings ====================
    # Push Notifications
    enable_push_notifications = models.BooleanField(default=True)
    firebase_server_key = models.CharField(max_length=255, blank=True)
    firebase_sender_id = models.CharField(max_length=50, blank=True)
    
    # Notification Types
    notify_on_withdrawal = models.BooleanField(default=True)
    notify_on_deposit = models.BooleanField(default=True)
    notify_on_referral = models.BooleanField(default=True)
    notify_on_bonus = models.BooleanField(default=True)
    notify_on_task_available = models.BooleanField(default=True)
    
    # ==================== Advanced Features ====================
    # Gamification
    enable_leaderboard = models.BooleanField(default=True)
    enable_badges = models.BooleanField(default=True)
    enable_achievements = models.BooleanField(default=True)
    enable_daily_streak = models.BooleanField(default=True)
    
    # Social Features
    enable_social_sharing = models.BooleanField(default=True)
    enable_user_profiles = models.BooleanField(default=True)
    enable_chat = models.BooleanField(default=False)
    enable_comments = models.BooleanField(default=False)
    
    # Admin Tools
    enable_debug_mode = models.BooleanField(
        default=False,
        help_text="Enable detailed error logging (disable in production)"
    )
    enable_api_logs = models.BooleanField(default=True)
    log_retention_days = models.IntegerField(
        default=30,
        help_text="Days to keep system logs"
    )
    
    # ==================== Timestamps ====================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_panel_systemsettings_last_modified_by'
    )
    
    class Meta:
        db_table = 'system_settings'
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'
    
    def __str__(self):
        return f"System Settings ({self.site_name})"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and SystemSettings.objects.exists():
            raise ValueError("Only one SystemSettings instance can exist")
        
        # Clear cache when settings are updated
        cache.delete('system_settings')
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create system settings singleton with caching"""
        settings = cache.get('system_settings')
        
        if settings is None:
            try:
                settings = cls.objects.first()
                if settings is None:
                    settings = cls.objects.create()
                cache.set('system_settings', settings, 3600)  # Cache for 1 hour
            except cls.DoesNotExist:
                settings = cls.objects.create()
                cache.set('system_settings', settings, 3600)
        
        return settings
    
    def check_app_version(self, platform, version_code):
        """
        Check if app version is allowed
        
        Args:
            platform: 'android' or 'ios'
            version_code: Integer version code
        
        Returns:
            dict with update requirements
        """
        if platform == 'android':
            current_code = self.android_version_code
            min_code = self.android_min_version_code
            force_update = self.android_force_update
            message = self.android_update_message
            app_link = self.android_app_link
            current_version = self.android_version
        elif platform == 'ios':
            current_code = self.ios_version_code
            min_code = self.ios_min_version_code
            force_update = self.ios_force_update
            message = self.ios_update_message
            app_link = self.ios_app_link
            current_version = self.ios_version
        else:
            return {
                'is_allowed': True,
                'update_required': False,
                'force_update': False
            }
        
        is_outdated = version_code < min_code
        update_available = version_code < current_code
        
        return {
            'is_allowed': not (is_outdated and force_update),
            'update_required': is_outdated,
            'update_available': update_available,
            'force_update': force_update and is_outdated,
            'message': message if (is_outdated or force_update) else '',
            'app_link': app_link,
            'current_version': current_version,
            'current_version_code': current_code,
            'min_required_version_code': min_code
        }
    
    def is_user_limit_exceeded(self, user, action_type):
        """
        Check if user has exceeded daily limits
        
        Args:
            user: User object
            action_type: 'ads', 'videos', 'tasks', 'surveys', 'earning'
        
        Returns:
            bool: True if limit exceeded
        """
        from security.models import ClickTracker
        from django.db.models import Sum
        
        today = timezone.now().date()
        
        if action_type == 'ads':
            count = ClickTracker.get_daily_action_count(user, 'ad_click', today)
            return count >= self.max_daily_ads
        
        elif action_type == 'videos':
            count = ClickTracker.get_daily_action_count(user, 'video_watch', today)
            return count >= self.max_daily_videos
        
        elif action_type == 'tasks':
            count = ClickTracker.get_daily_action_count(user, 'task_complete', today)
            return count >= self.max_daily_tasks
        
        elif action_type == 'surveys':
            count = ClickTracker.get_daily_action_count(user, 'survey_complete', today)
            return count >= self.max_daily_surveys
        
        elif action_type == 'earning':
            # Check total earnings for today
            from api.transactions.models import Transaction
            daily_earning = Transaction.objects.filter(
                user=user,
                transaction_type='earning',
                created_at__date=today,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            return daily_earning >= self.max_daily_earning_limit
        
        return False
    
    def to_dict(self):
        """Convert settings to dictionary"""
        return {
            'site_name': self.site_name,
            'currency_code': self.currency_code,
            'currency_symbol': self.currency_symbol,
            'min_withdrawal': float(self.min_withdrawal_amount),
            'max_withdrawal': float(self.max_withdrawal_amount),
            'referral_enabled': self.enable_referral,
            'maintenance_mode': self.maintenance_mode,
            'version': {
                'android': self.android_version,
                'ios': self.ios_version,
                'web': self.web_version
            }
        }


class SiteNotification(models.Model):
    """Site-wide notifications and announcements"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    NOTIFICATION_TYPE_CHOICES = [
        ('INFO', 'Information'),
        ('SUCCESS', 'Success'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('MAINTENANCE', 'Maintenance'),
        ('UPDATE', 'Update'),
        ('PROMOTION', 'Promotion'),
    ]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES, default='INFO')
    is_active = models.BooleanField(default=True)
    show_on_login = models.BooleanField(default=False)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(blank=True, null=True)
    priority = models.IntegerField(default=0)  # Higher number = higher priority
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'site_notifications'
        ordering = ['-priority', '-created_at']
        verbose_name = 'Site Notification'
        verbose_name_plural = 'Site Notifications'
    
    def __str__(self):
        return f"{self.title} ({self.get_notification_type_display()})"
    
    def is_current(self):
        """Check if notification is currently active"""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True


class SiteContent(models.Model):
    """Dynamic site content (pages, sections, etc.)"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    CONTENT_TYPE_CHOICES = [
        ('PAGE', 'Page'),
        ('SECTION', 'Section'),
        ('BANNER', 'Banner'),
        ('FOOTER', 'Footer'),
        ('SIDEBAR', 'Sidebar'),
        ('POPUP', 'Popup'),
    ]
    
    identifier = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='PAGE')
    is_active = models.BooleanField(default=True)
    language = models.CharField(max_length=10, default='en')
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=500, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'site_contents'
        ordering = ['order', 'title']
        verbose_name = 'Site Content'
        verbose_name_plural = 'Site Contents'
        unique_together = ['identifier', 'language']
    
    def __str__(self):
        return f"{self.title} ({self.get_content_type_display()})"
from .endpoint_toggle import EndpointToggle
