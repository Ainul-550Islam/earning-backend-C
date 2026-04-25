# earning_backend/api/notifications/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Sum, Avg
from django.db.models.functions import TruncDate
import uuid
import json
from datetime import timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any
from enum import Enum
from django.conf import settings

User = get_user_model()

class NotificationCategory(Enum):
    """Enum for notification categories"""
    SYSTEM = 'system'
    FINANCIAL = 'financial'
    TASK_RELATED = 'task_related'
    SECURITY = 'security'
    MARKETING = 'marketing'
    SOCIAL = 'social'
    SUPPORT = 'support'
    ACHIEVEMENT = 'achievement'
    GAMIFICATION = 'gamification'
    ADMIN = 'admin'


class NotificationChannel(Enum):
    """Enum for notification channels"""
    IN_APP = 'in_app'
    PUSH = 'push'
    EMAIL = 'email'
    SMS = 'sms'
    TELEGRAM = 'telegram'
    WHATSAPP = 'whatsapp'
    BROWSER = 'browser'
    ALL = 'all'


class NotificationPriority(Enum):
    """Enum for notification priorities"""
    LOWEST = 'lowest'
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'
    CRITICAL = 'critical'


class NotificationStatus(Enum):
    """Enum for notification statuses"""
    DRAFT = 'draft'
    SCHEDULED = 'scheduled'
    PENDING = 'pending'
    SENDING = 'sending'
    SENT = 'sent'
    DELIVERED = 'delivered'
    READ = 'read'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'


class Notification(models.Model):
    """
    Main Notification Model with all features
    """
    
    # Notification Types with detailed categorization
    NOTIFICATION_TYPES = (
        # System Notifications
        ('system_update', 'System Update'),
        ('maintenance', 'System Maintenance'),
        ('app_update', 'App Update'),
        ('new_feature', 'New Feature'),
        ('bug_fix', 'Bug Fix'),
        ('announcement', 'Announcement'),
        ('news', 'News'),
        
        # Financial Notifications
        ('payment_success', 'Payment Success'),
        ('payment_failed', 'Payment Failed'),
        ('withdrawal_success', 'Withdrawal Success'),
        ('withdrawal_failed', 'Withdrawal Failed'),
        ('withdrawal_pending', 'Withdrawal Pending'),
        ('withdrawal_approved', 'Withdrawal Approved'),
        ('withdrawal_rejected', 'Withdrawal Rejected'),
        ('deposit_success', 'Deposit Success'),
        ('deposit_failed', 'Deposit Failed'),
        ('refund', 'Refund'),
        ('chargeback', 'Chargeback'),
        ('subscription_renewal', 'Subscription Renewal'),
        ('subscription_expired', 'Subscription Expired'),
        ('wallet_credited', 'Wallet Credited'),
        ('wallet_debited', 'Wallet Debited'),
        ('low_balance', 'Low Balance'),
        ('bonus_added', 'Bonus Added'),
        ('cashback', 'Cashback'),
        ('reward_points', 'Reward Points'),
        
        # Task Related Notifications
        ('task_assigned', 'Task Assigned'),
        ('task_completed', 'Task Completed'),
        ('task_rejected', 'Task Rejected'),
        ('task_approved', 'Task Approved'),
        ('task_expired', 'Task Expired'),
        ('task_reminder', 'Task Reminder'),
        ('task_deadline', 'Task Deadline'),
        ('task_reward', 'Task Reward'),
        ('task_verification', 'Task Verification'),
        ('task_dispute', 'Task Dispute'),
        ('task_available', 'New Task Available'),
        ('task_limit_reached', 'Task Limit Reached'),
        
        # Security Notifications
        ('login_success', 'Login Success'),
        ('login_failed', 'Login Failed'),
        ('login_new_device', 'Login from New Device'),
        ('login_new_location', 'Login from New Location'),
        ('password_changed', 'Password Changed'),
        ('password_reset', 'Password Reset'),
        ('two_factor_enabled', '2FA Enabled'),
        ('two_factor_disabled', '2FA Disabled'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('account_locked', 'Account Locked'),
        ('account_unlocked', 'Account Unlocked'),
        ('email_verified', 'Email Verified'),
        ('phone_verified', 'Phone Verified'),
        ('kyc_approved', 'KYC Approved'),
        ('kyc_rejected', 'KYC Rejected'),
        ('kyc_pending', 'KYC Pending'),
        ('kyc_submitted', 'KYC Submitted'),
        ('fraud_detected', 'Fraud Detected'),
        ('security_alert', 'Security Alert'),
        
        # Marketing Notifications
        ('promotion', 'Promotion'),
        ('offer', 'Offer'),
        ('discount', 'Discount'),
        ('coupon', 'Coupon'),
        ('sale', 'Sale'),
        ('flash_sale', 'Flash Sale'),
        ('new_arrival', 'New Arrival'),
        ('restock', 'Restock'),
        ('price_drop', 'Price Drop'),
        ('abandoned_cart', 'Abandoned Cart'),
        ('wishlist', 'Wishlist'),
        ('product_review', 'Product Review'),
        ('survey', 'Survey'),
        ('feedback', 'Feedback'),
        
        # Social Notifications
        ('friend_request', 'Friend Request'),
        ('friend_accepted', 'Friend Accepted'),
        ('friend_rejected', 'Friend Rejected'),
        ('follow', 'Follow'),
        ('unfollow', 'Unfollow'),
        ('message', 'Message'),
        ('comment', 'Comment'),
        ('like', 'Like'),
        ('share', 'Share'),
        ('mention', 'Mention'),
        ('tag', 'Tag'),
        ('invite', 'Invite'),
        ('group_invite', 'Group Invite'),
        ('group_join', 'Group Join'),
        ('group_leave', 'Group Leave'),
        ('event_invite', 'Event Invite'),
        ('event_reminder', 'Event Reminder'),
        
        # Referral Notifications
        ('referral_signup', 'Referral Signup'),
        ('referral_completed', 'Referral Completed'),
        ('referral_reward', 'Referral Reward'),
        ('referral_expired', 'Referral Expired'),
        # CPAlead / Offerwall specific
        ('offer_completed', 'Offer/Offerwall Completed'),
        ('offer_available', 'New Offer Available'),
        ('postback_received', 'Advertiser Postback Received'),
        ('postback_failed', 'Postback Failed'),
        ('ip_fraud_blocked', 'IP/Fraud Blocked'),
        ('account_suspended', 'Account Suspended'),
        ('account_reinstated', 'Account Reinstated'),
        ('account_warning', 'Account Warning'),
        ('affiliate_commission', 'Affiliate Commission Earned'),
        ('sub_affiliate_earn', 'Sub-Affiliate Earning'),
        ('leaderboard_update', 'Leaderboard Position Update'),
        ('publisher_payout', 'Publisher Payout'),
        ('conversion_received', 'Conversion Received'),
        ('campaign_live', 'Campaign Went Live'),
        ('campaign_paused', 'Campaign Paused'),
        ('referral_bonus', 'Referral Bonus'),
        ('team_bonus', 'Team Bonus'),
        
        # Support Notifications
        ('ticket_created', 'Ticket Created'),
        ('ticket_updated', 'Ticket Updated'),
        ('ticket_resolved', 'Ticket Resolved'),
        ('ticket_closed', 'Ticket Closed'),
        ('ticket_reply', 'Ticket Reply'),
        ('ticket_escalated', 'Ticket Escalated'),
        ('live_chat', 'Live Chat'),
        ('chat_message', 'Chat Message'),
        ('chat_request', 'Chat Request'),
        ('faq_suggestion', 'FAQ Suggestion'),
        
        # Achievement Notifications
        ('level_up', 'Level Up'),
        ('badge_earned', 'Badge Earned'),
        ('achievement_unlocked', 'Achievement Unlocked'),
        ('milestone_reached', 'Milestone Reached'),
        ('rank_up', 'Rank Up'),
        ('streak', 'Streak'),
        ('daily_streak', 'Daily Streak'),
        ('weekly_streak', 'Weekly Streak'),
        ('monthly_streak', 'Monthly Streak'),
        ('challenge_completed', 'Challenge Completed'),
        ('contest_won', 'Contest Won'),
        ('contest_participation', 'Contest Participation'),
        
        # Gamification Notifications
        ('daily_reward', 'Daily Reward'),
        ('streak_reward', 'Streak Reward'),
        ('weekly_reward', 'Weekly Reward'),
        ('monthly_reward', 'Monthly Reward'),
        ('spin_wheel', 'Spin Wheel'),
        ('scratch_card', 'Scratch Card'),
        ('lucky_draw', 'Lucky Draw'),
        ('quiz_completed', 'Quiz Completed'),
        ('trivia_winner', 'Trivia Winner'),
        ('mini_game', 'Mini Game'),
        
        # Admin Notifications
        ('user_registered', 'User Registered'),
        ('user_verified', 'User Verified'),
        ('user_blocked', 'User Blocked'),
        ('user_deleted', 'User Deleted'),
        ('content_reported', 'Content Reported'),
        ('content_removed', 'Content Removed'),
        ('content_approved', 'Content Approved'),
        ('moderation', 'Moderation'),
        ('admin_alert', 'Admin Alert'),
        ('system_error', 'System Error'),
        ('database_backup', 'Database Backup'),
        ('server_maintenance', 'Server Maintenance'),
        
        # Ad & Engagement Notifications
        ('ad_viewed', 'Ad Viewed'),
        ('ad_clicked', 'Ad Clicked'),
        ('ad_completed', 'Ad Completed'),
        ('video_watched', 'Video Watched'),
        ('article_read', 'Article Read'),
        ('app_installed', 'App Installed'),
        ('app_reviewed', 'App Reviewed'),
        ('survey_completed', 'Survey Completed'),
        ('poll_voted', 'Poll Voted'),
        
        # Custom Notifications
        ('custom', 'Custom'),
        ('reminder', 'Reminder'),
        ('alert', 'Alert'),
        ('warning', 'Warning'),
        ('info', 'Information'),
        ('success', 'Success'),
        ('error', 'Error'),
        ('general', 'General'),
    )
    
    # Priority Levels
    PRIORITY_LEVELS = (
        ('lowest', 'Lowest'),
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        ('critical', 'Critical'),
    )
    
    # Status Choices
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('pending', 'Pending'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    )
    
    # Channel Choices
    CHANNEL_CHOICES = (
        ('in_app', 'In-App'),
        ('push', 'Push Notification'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('telegram', 'Telegram'),
        ('whatsapp', 'WhatsApp'),
        ('browser', 'Browser Push'),
        ('all', 'All Channels'),
    )
    
    # Language Choices
    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('bn', 'বাংলা'),
        ('hi', 'हिन्दी'),
        ('ar', 'العربية'),
        ('es', 'Español'),
        ('fr', 'Français'),
        ('de', 'Deutsch'),
        ('pt', 'Português'),
        ('ru', 'Русский'),
        ('zh', '中文'),
        ('ja', '日本語'),
        ('ko', '한국어'),
    )
    
    # Device Type Choices
    DEVICE_TYPES = (
        ('web', 'Web Browser'),
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('windows', 'Windows'),
        ('mac', 'macOS'),
        ('linux', 'Linux'),
        ('smart_tv', 'Smart TV'),
        ('smart_watch', 'Smart Watch'),
        ('tablet', 'Tablet'),
        ('desktop', 'Desktop'),
        ('mobile', 'Mobile'),
        ('unknown', 'Unknown'),
    )
    
    # Platform Choices
    PLATFORM_CHOICES = (
        ('web', 'Web'),
        ('android_app', 'Android App'),
        ('ios_app', 'iOS App'),
        ('windows_app', 'Windows App'),
        ('mac_app', 'macOS App'),
        ('progressive_web_app', 'Progressive Web App'),
        ('api', 'API'),
        ('admin_panel', 'Admin Panel'),
    )
    
    # ==================== CORE FIELDS ====================
    
    # Unique Identifier
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Notification ID'
    )
    
    # Recipient Information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_notifications',
        verbose_name='Recipient User',
        help_text='User who will receive this notification')
    
    # Title and Message
    title = models.CharField(
        max_length=255,
        verbose_name='Notification Title',
        help_text='Title of the notification')
    
    message = models.TextField(
        verbose_name='Notification Message',
        help_text='Detailed message content'
    )
    
    # ==================== CLASSIFICATION ====================
    
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        default='general',
        verbose_name='Notification Type',
        help_text='Type/category of notification')
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_LEVELS,
        default='medium',
        verbose_name='Priority Level',
        help_text='Importance level of notification')
    
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default='in_app',
        verbose_name='Delivery Channel',
        help_text='Channel through which to send notification')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='Notification Status',
        help_text='Current status of notification')
    
    # ==================== STATUS TRACKING ====================
    
    is_read = models.BooleanField(
        default=False,
        verbose_name='Is Read',
        help_text='Whether user has read the notification'
    )
    
    is_delivered = models.BooleanField(
        default=False,
        verbose_name='Is Delivered',
        help_text='Whether notification was delivered successfully'
    )
    
    is_sent = models.BooleanField(
        default=False,
        verbose_name='Is Sent',
        help_text='Whether notification was sent to delivery service'
    )
    
    is_archived = models.BooleanField(
        default=False,
        verbose_name='Is Archived',
        help_text='Whether notification is archived'
    )
    
    is_pinned = models.BooleanField(
        default=False,
        verbose_name='Is Pinned',
        help_text='Whether notification is pinned for user'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At',
        help_text='When notification was created'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At',
        help_text='When notification was last updated'
    )
    
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Scheduled For',
        help_text='When to send notification (if scheduled)'
    )
    
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Sent At',
        help_text='When notification was sent'
    )
    
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Delivered At',
        help_text='When notification was delivered'
    )
    
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Read At',
        help_text='When user read the notification'
    )
    
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Archived At',
        help_text='When notification was archived'
    )
    
    expire_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Expire Date',
        help_text='When notification will expire/auto-delete'
    )
    
    # ==================== FLEXIBLE DATA (METADATA) ====================
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata',
        help_text='Additional flexible data in JSON format'
    )
    
    # ==================== ADVANCED FEATURES ====================
    
    # Visual Elements
    image_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name='Image URL',
        help_text='URL of notification image'
    )
    
    icon_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name='Icon URL',
        help_text='URL of notification icon')
    
    thumbnail_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name='Thumbnail URL',
        help_text='URL of notification thumbnail')
    
    # Action Elements
    action_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name='Action URL',
        help_text='URL to navigate when notification is clicked')
    
    action_text = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Action Text',
        help_text='Text for action button')
    
    deep_link = models.CharField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name='Deep Link',
        help_text='App deep link for mobile notifications')
    
    # Device Information
    device_type = models.CharField(
        max_length=50,
        choices=DEVICE_TYPES,
        default='unknown',
        verbose_name='Device Type',
        help_text='Type of device receiving notification')
    
    platform = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES,
        default='web',
        verbose_name='Platform',
        help_text='Platform where notification will be shown')
    
    # Language and Localization
    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default='en',
        verbose_name='Language',
        help_text='Language of notification content')
    
    # Analytics
    click_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Click Count',
        help_text='Number of times notification was clicked'
    )
    
    view_count = models.PositiveIntegerField(
        default=0,
        verbose_name='View Count',
        help_text='Number of times notification was viewed'
    )
    
    impression_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Impression Count',
        help_text='Number of times notification was shown'
    )
    
    # Delivery Tracking
    delivery_attempts = models.PositiveIntegerField(
        default=0,
        verbose_name='Delivery Attempts',
        help_text='Number of delivery attempts made'
    )
    
    last_delivery_attempt = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Last Delivery Attempt',
        help_text='When last delivery attempt was made'
    )
    
    delivery_error = models.TextField(
        blank=True,
        null=True,
        verbose_name='Delivery Error',
        help_text='Error message if delivery failed'
    )
    
    # Parent-Child Relationships
    parent_notification = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name='Parent Notification',
        help_text='Parent notification for threaded notifications')
    
    # Grouping
    group_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Group ID',
        help_text='ID for grouping related notifications')
    
    # Tags
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Tags',
        help_text='Tags for filtering and categorization'
    )
    
    # Campaign Tracking
    campaign_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Campaign ID',
        help_text='ID of marketing campaign')
    
    campaign_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Campaign Name',
        help_text='Name of marketing campaign')
    
    # A/B Testing
    variant = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Variant',
        help_text='A/B testing variant identifier')
    
    # Priority Boost
    priority_boost = models.IntegerField(
        default=0,
        verbose_name='Priority Boost',
        help_text='Temporary priority boost value'
    )
    
    # Expiration Rules
    auto_delete_after_read = models.BooleanField(
        default=False,
        verbose_name='Auto Delete After Read',
        help_text='Automatically delete after user reads it'
    )
    
    auto_delete_after_days = models.PositiveIntegerField(
        default=30,
        verbose_name='Auto Delete After Days',
        help_text='Automatically delete after specified days'
    )
    
    # Notification Sound
    sound_enabled = models.BooleanField(
        default=True,
        verbose_name='Sound Enabled',
        help_text='Play sound when notification arrives'
    )
    
    sound_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Sound Name',
        help_text='Name of notification sound')
    
    # Vibration
    vibration_enabled = models.BooleanField(
        default=True,
        verbose_name='Vibration Enabled',
        help_text='Vibrate when notification arrives'
    )
    
    vibration_pattern = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Vibration Pattern',
        help_text='Pattern for vibration')
    
    # LED Light
    led_color = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='LED Color',
        help_text='LED light color for notification')
    
    led_blink_pattern = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='LED Blink Pattern',
        help_text='Blink pattern for LED light')
    
    # Notification Badge
    badge_count = models.PositiveIntegerField(
        default=1,
        verbose_name='Badge Count',
        help_text='Badge count to show on app icon'
    )
    
    # Rich Content
    rich_content = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Rich Content',
        help_text='Rich content for notification (images, buttons, etc.)'
    )
    
    # Custom Styling
    custom_style = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Custom Style',
        help_text='Custom CSS/styling for notification'
    )
    
    # Notification Position
    position = models.CharField(
        max_length=50,
        default='top-right',
        choices=(
            ('top-left', 'Top Left'),
            ('top-center', 'Top Center'),
            ('top-right', 'Top Right'),
            ('bottom-left', 'Bottom Left'),
            ('bottom-center', 'Bottom Center'),
            ('bottom-right', 'Bottom Right'),
            ('center', 'Center'),
        ),
        verbose_name='Position',
        help_text='Position to show notification'
    )
    
    # Animation
    animation = models.CharField(
        max_length=50,
        default='fade',
        choices=(
            ('fade', 'Fade'),
            ('slide', 'Slide'),
            ('bounce', 'Bounce'),
            ('zoom', 'Zoom'),
            ('flip', 'Flip'),
            ('none', 'None'),
        ),
        verbose_name='Animation',
        help_text='Animation for notification display'
    )
    
    # Dismissible
    is_dismissible = models.BooleanField(
        default=True,
        verbose_name='Is Dismissible',
        help_text='Whether user can dismiss notification'
    )
    
    # Auto Dismiss
    auto_dismiss_after = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Auto Dismiss After',
        help_text='Auto dismiss after seconds (null for manual dismiss)'
    )
    
    # Progress Indicator
    show_progress = models.BooleanField(
        default=False,
        verbose_name='Show Progress',
        help_text='Show progress indicator'
    )
    
    progress_value = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        verbose_name='Progress Value',
        help_text='Progress value (0-100)'
    )
    
    # User Feedback
    feedback_enabled = models.BooleanField(
        default=False,
        verbose_name='Feedback Enabled',
        help_text='Enable user feedback for notification'
    )
    
    feedback_options = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Feedback Options',
        help_text='Options for user feedback'
    )
    
    # Engagement Tracking
    engagement_score = models.FloatField(
        default=0.0,
        verbose_name='Engagement Score',
        help_text='Score based on user engagement'
    )
    
    # Cost Tracking
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.00,
        verbose_name='Cost',
        help_text='Cost of sending notification')
    
    cost_currency = models.CharField(
        max_length=3,
        default='USD',
        verbose_name='Cost Currency',
        help_text='Currency for cost calculation')
    
    # Performance Metrics
    open_rate = models.FloatField(
        default=0.0,
        verbose_name='Open Rate',
        help_text='Rate at which notification was opened'
    )
    
    click_through_rate = models.FloatField(
        default=0.0,
        verbose_name='Click Through Rate',
        help_text='Rate at which notification was clicked'
    )
    
    conversion_rate = models.FloatField(
        default=0.0,
        verbose_name='Conversion Rate',
        help_text='Rate at which notification led to conversion'
    )
    
    # Batch Information
    batch_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name='Batch ID',
        help_text='ID for batch notifications'
    )
    
    batch_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Batch Name',
        help_text='Name for batch notifications')
    
    # Retry Configuration
    max_retries = models.PositiveIntegerField(
        default=3,
        verbose_name='Max Retries',
        help_text='Maximum number of delivery retries'
    )
    
    retry_interval = models.PositiveIntegerField(
        default=300,
        verbose_name='Retry Interval',
        help_text='Seconds between retry attempts'
    )
    
    # Security
    is_encrypted = models.BooleanField(
        default=False,
        verbose_name='Is Encrypted',
        help_text='Whether notification content is encrypted'
    )
    
    encryption_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Encryption Key',
        help_text='Key for encryption/decryption')
    
    # Audit Logging
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_notifications',
        verbose_name='Created By',
        help_text='User who created the notification')
    
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_notifications',
        verbose_name='Modified By',
        help_text='User who last modified the notification')
    
    # Versioning
    version = models.PositiveIntegerField(
        default=1,
        verbose_name='Version',
        help_text='Version number of notification'
    )
    
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='next_versions',
        verbose_name='Previous Version',
        help_text='Previous version of notification')
    
    # Archive Information
    archive_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name='Archive Reason',
        help_text='Reason for archiving notification'
    )
    
    # Deletion Information
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='Is Deleted',
        help_text='Whether notification is soft deleted'
    )
    
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Deleted At',
        help_text='When notification was soft deleted'
    )
    
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_notifications',
        verbose_name='Deleted By',
        help_text='User who deleted the notification')
    
    # Custom Fields
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Custom Fields',
        help_text='Additional custom fields'
    )
    
    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['priority']),
            models.Index(fields=['status']),
            models.Index(fields=['channel']),
            models.Index(fields=['scheduled_for']),
            models.Index(fields=['expire_date']),
            models.Index(fields=['batch_id']),
            models.Index(fields=['campaign_id']),
            models.Index(fields=['group_id']),
            models.Index(fields=['is_deleted']),
            models.Index(fields=['language']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username} ({self.get_status_display()})"
    
    # ==================== MODEL METHODS ====================
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Validate scheduled_for
        if self.scheduled_for and self.scheduled_for < timezone.now():
            raise ValidationError(
                {'scheduled_for': 'Scheduled time cannot be in the past.'}
            )
        
        # Validate expire_date
        if self.expire_date and self.expire_date < timezone.now():
            raise ValidationError(
                {'expire_date': 'Expire date cannot be in the past.'}
            )
        
        # Validate metadata JSON
        try:
            if self.metadata:
                json.dumps(self.metadata)
        except (TypeError, ValueError):
            raise ValidationError(
                {'metadata': 'Metadata must be valid JSON.'}
            )
    
    def save(self, *args, **kwargs):
        """Custom save logic"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def mark_as_read(self, save=True):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.status = 'read'
            if save:
                self.save()
    
    def mark_as_unread(self, save=True):
        """Mark notification as unread"""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.status = 'delivered' if self.is_delivered else 'sent'
            if save:
                self.save()
    
    def mark_as_sent(self, save=True):
        """Mark notification as sent"""
        if not self.is_sent:
            self.is_sent = True
            self.sent_at = timezone.now()
            self.status = 'sent'
            if save:
                self.save()
    
    def mark_as_delivered(self, save=True):
        """Mark notification as delivered"""
        if not self.is_delivered:
            self.is_delivered = True
            self.delivered_at = timezone.now()
            self.status = 'delivered'
            if save:
                self.save()
    
    def mark_as_failed(self, error_message=None, save=True):
        """Mark notification as failed"""
        self.status = 'failed'
        self.delivery_error = error_message
        if save:
            self.save()
    
    def increment_click_count(self, save=True):
        """Increment click count"""
        self.click_count += 1
        if save:
            self.save()
    
    def increment_view_count(self, save=True):
        """Increment view count"""
        self.view_count += 1
        if save:
            self.save()
    
    def increment_impression_count(self, save=True):
        """Increment impression count"""
        self.impression_count += 1
        if save:
            self.save()
    
    def is_expired(self):
        """Check if notification is expired"""
        if self.expire_date:
            return timezone.now() > self.expire_date
        return False
    
    def should_auto_delete(self):
        """Check if notification should be auto-deleted"""
        if self.auto_delete_after_read and self.is_read:
            return True
        if self.auto_delete_after_days:
            expiry_date = self.created_at + timedelta(days=self.auto_delete_after_days)
            return timezone.now() > expiry_date
        return False
    
    def get_priority_score(self):
        """Calculate priority score"""
        priority_scores = {
            'lowest': 1,
            'low': 2,
            'medium': 3,
            'high': 4,
            'urgent': 5,
            'critical': 6,
        }
        base_score = priority_scores.get(self.priority, 3)
        return base_score + self.priority_boost
    
    def get_icon_url(self):
        """Get icon URL with fallback"""
        if self.icon_url:
            return self.icon_url
        
        # Default icons based on notification type
        icon_map = {
            'payment_success': '/static/icons/payment-success.png',
            'payment_failed': '/static/icons/payment-failed.png',
            'withdrawal_success': '/static/icons/withdrawal-success.png',
            'task_completed': '/static/icons/task-completed.png',
            'task_assigned': '/static/icons/task-assigned.png',
            'referral_signup': '/static/icons/referral.png',
            'security_alert': '/static/icons/security.png',
            'login_new_device': '/static/icons/device.png',
            'kyc_approved': '/static/icons/kyc-approved.png',
            'level_up': '/static/icons/level-up.png',
            'achievement_unlocked': '/static/icons/achievement.png',
            'bonus_added': '/static/icons/bonus.png',
            'wallet_credited': '/static/icons/wallet.png',
            'system_update': '/static/icons/system.png',
            'promotion': '/static/icons/promotion.png',
            'support_reply': '/static/icons/support.png',
            'friend_request': '/static/icons/friend.png',
            'message': '/static/icons/message.png',
            'announcement': '/static/icons/announcement.png',
            'alert': '/static/icons/alert.png',
            'warning': '/static/icons/warning.png',
            'success': '/static/icons/success.png',
            'error': '/static/icons/error.png',
            'info': '/static/icons/info.png',
        }
        
        return icon_map.get(self.notification_type, '/static/icons/notification.png')
    
    def get_metadata_value(self, key, default=None):
        """Get value from metadata"""
        return self.metadata.get(key, default)
    
    def set_metadata_value(self, key, value):
        """Set value in metadata"""
        self.metadata[key] = value
    
    def update_metadata(self, updates):
        """Update multiple metadata values"""
        self.metadata.update(updates)
    
    def add_tag(self, tag):
        """Add tag to notification"""
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag):
        """Remove tag from notification"""
        if tag in self.tags:
            self.tags.remove(tag)
    
    def has_tag(self, tag):
        """Check if notification has tag"""
        return tag in self.tags
    
    def get_age_in_seconds(self):
        """Get age of notification in seconds"""
        return (timezone.now() - self.created_at).total_seconds()
    
    def get_age_in_minutes(self):
        """Get age of notification in minutes"""
        return self.get_age_in_seconds() / 60
    
    def get_age_in_hours(self):
        """Get age of notification in hours"""
        return self.get_age_in_minutes() / 60
    
    def get_age_in_days(self):
        """Get age of notification in days"""
        return self.get_age_in_hours() / 24
    
    def get_formatted_age(self):
        """Get formatted age string"""
        age_seconds = self.get_age_in_seconds()
        
        if age_seconds < 60:
            return f"{int(age_seconds)} seconds ago"
        elif age_seconds < 3600:
            minutes = int(age_seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif age_seconds < 86400:
            hours = int(age_seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(age_seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
    
    def can_retry_delivery(self):
        """Check if notification can be retried"""
        if self.status in ['sent', 'failed'] and self.delivery_attempts < self.max_retries:
            if self.last_delivery_attempt:
                retry_time = self.last_delivery_attempt + timedelta(seconds=self.retry_interval)
                return timezone.now() > retry_time
            return True
        return False
    
    def prepare_for_retry(self):
        """Prepare notification for retry"""
        self.delivery_attempts += 1
        self.last_delivery_attempt = timezone.now()
        self.status = 'pending'
        self.delivery_error = None
    
    def calculate_engagement_score(self):
        """Calculate engagement score"""
        score = 0.0
        
        # Base score for delivery
        if self.is_delivered:
            score += 10.0
        
        # Score for reading
        if self.is_read:
            score += 20.0
            # Faster reading = higher score
            if self.sent_at and self.read_at:
                read_time = (self.read_at - self.sent_at).total_seconds()
                if read_time < 60:  # Read within 1 minute
                    score += 30.0
                elif read_time < 300:  # Read within 5 minutes
                    score += 20.0
                elif read_time < 1800:  # Read within 30 minutes
                    score += 10.0
        
        # Score for clicks
        if self.click_count > 0:
            score += self.click_count * 15.0
        
        # Score for views
        if self.view_count > 0:
            score += self.view_count * 5.0
        
        # Penalty for failures
        if self.status == 'failed':
            score -= 50.0
        
        self.engagement_score = max(0.0, score)
        return self.engagement_score
    
    def update_performance_metrics(self):
        """Update performance metrics"""
        if self.impression_count > 0:
            self.open_rate = (self.view_count / self.impression_count) * 100
            self.click_through_rate = (self.click_count / self.impression_count) * 100
        
        # Conversion rate would need business logic
        # This is a placeholder
        self.conversion_rate = self.click_through_rate * 0.1  # Example
    
    def to_dict(self):
        """Convert notification to dictionary"""
        return {
            'id': str(self.id),
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type,
            'priority': self.priority,
            'status': self.status,
            'is_read': self.is_read,
            'is_delivered': self.is_delivered,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'expire_date': self.expire_date.isoformat() if self.expire_date else None,
            'metadata': self.metadata,
            'image_url': self.image_url,
            'icon_url': self.icon_url or self.get_icon_url(),
            'action_url': self.action_url,
            'action_text': self.action_text,
            'deep_link': self.deep_link,
            'device_type': self.device_type,
            'platform': self.platform,
            'language': self.language,
            'click_count': self.click_count,
            'view_count': self.view_count,
            'impression_count': self.impression_count,
            'tags': self.tags,
            'campaign_id': self.campaign_id,
            'campaign_name': self.campaign_name,
            'group_id': self.group_id,
            'priority_boost': self.priority_boost,
            'engagement_score': self.engagement_score,
            'formatted_age': self.get_formatted_age(),
            'is_expired': self.is_expired(),
            'should_auto_delete': self.should_auto_delete(),
        }
    
    def clone(self, new_user=None, **kwargs):
        """Clone notification"""
        clone_fields = [
            'title', 'message', 'notification_type', 'priority', 'channel',
            'image_url', 'icon_url', 'action_url', 'action_text', 'deep_link',
            'device_type', 'platform', 'language', 'metadata', 'tags',
            'campaign_id', 'campaign_name', 'group_id', 'rich_content',
            'custom_style', 'position', 'animation', 'is_dismissible',
            'auto_dismiss_after', 'show_progress', 'progress_value',
            'feedback_enabled', 'feedback_options', 'sound_enabled',
            'sound_name', 'vibration_enabled', 'vibration_pattern',
            'led_color', 'led_blink_pattern', 'badge_count',
        ]
        
        clone_data = {}
        for field in clone_fields:
            clone_data[field] = getattr(self, field)
        
        # Update with kwargs
        clone_data.update(kwargs)
        
        # Set user
        if new_user:
            clone_data['user'] = new_user
        else:
            clone_data['user'] = self.user
        
        # Create clone
        clone = Notification.objects.create(**clone_data)
        return clone
    
    def send_test_notification(self):
        """Send test notification (for debugging)"""
        from ._services_core import NotificationService
        return NotificationService.send_test_notification(self)
    
    def archive(self, reason=None, save=True):
        """Archive notification"""
        self.is_archived = True
        self.archived_at = timezone.now()
        self.archive_reason = reason
        if save:
            self.save()
    
    def unarchive(self, save=True):
        """Unarchive notification"""
        self.is_archived = False
        self.archived_at = None
        self.archive_reason = None
        if save:
            self.save()
    
    def pin(self, save=True):
        """Pin notification"""
        self.is_pinned = True
        if save:
            self.save()
    
    def unpin(self, save=True):
        """Unpin notification"""
        self.is_pinned = False
        if save:
            self.save()
    
    def soft_delete(self, deleted_by=None, save=True):
        """Soft delete notification"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        if save:
            self.save()
    
    def restore(self, save=True):
        """Restore soft deleted notification"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        if save:
            self.save()
    
    def get_replies(self):
        """Get replies to this notification"""
        return self.replies.filter(is_deleted=False)
    
    def add_reply(self, title, message, user=None, **kwargs):
        """Add reply to notification"""
        if not user:
            user = self.user
        
        reply = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            parent_notification=self,
            notification_type='message',
            channel='in_app',
            **kwargs
        )
        return reply
    
    def get_thread_depth(self):
        """Get depth of notification thread"""
        depth = 0
        current = self
        while current.parent_notification:
            depth += 1
            current = current.parent_notification
        return depth
    
    def get_thread_ancestors(self):
        """Get all ancestors in thread"""
        ancestors = []
        current = self.parent_notification
        while current:
            ancestors.append(current)
            current = current.parent_notification
        return ancestors
    
    def get_thread_descendants(self):
        """Get all descendants in thread"""
        from django.db.models import Q
        
        def get_descendants(notification, descendants):
            replies = notification.get_replies()
            for reply in replies:
                descendants.append(reply)
                get_descendants(reply, descendants)
        
        descendants = []
        get_descendants(self, descendants)
        return descendants
    
    def is_part_of_thread(self):
        """Check if notification is part of a thread"""
        return bool(self.parent_notification or self.replies.exists())
    
    def merge_metadata(self, new_metadata):
        """Merge new metadata with existing"""
        import copy
        merged = copy.deepcopy(self.metadata)
        
        def merge_dicts(d1, d2):
            for key, value in d2.items():
                if key in d1 and isinstance(d1[key], dict) and isinstance(value, dict):
                    merge_dicts(d1[key], value)
                else:
                    d1[key] = value
        
        merge_dicts(merged, new_metadata)
        self.metadata = merged
    
    def validate_for_delivery(self):
        """Validate notification for delivery"""
        errors = []
        
        # Check required fields
        if not self.user:
            errors.append("User is required")
        
        if not self.title:
            errors.append("Title is required")
        
        if not self.message:
            errors.append("Message is required")
        
        # Check expiration
        if self.is_expired():
            errors.append("Notification has expired")
        
        # Check deletion status
        if self.is_deleted:
            errors.append("Notification is deleted")
        
        # Check archived status
        if self.is_archived:
            errors.append("Notification is archived")
        
        # Check scheduled time
        if self.scheduled_for and self.scheduled_for > timezone.now():
            errors.append("Notification is scheduled for future delivery")
        
        return errors
    
    def get_delivery_channels(self):
        """Get list of delivery channels"""
        if self.channel == 'all':
            return ['in_app', 'push', 'email', 'sms']
        return [self.channel]
    
    def estimate_cost(self):
        """Estimate cost of sending notification"""
        channel_costs = {
            'in_app': Decimal('0.0000'),
            'push': Decimal('0.0005'),
            'email': Decimal('0.0010'),
            'sms': Decimal('0.0100'),
            'telegram': Decimal('0.0000'),
            'whatsapp': Decimal('0.0005'),
            'browser': Decimal('0.0000'),
        }
        
        cost = channel_costs.get(self.channel, Decimal('0.0000'))
        
        # Add cost for retries
        if self.delivery_attempts > 0:
            cost += cost * Decimal(str(self.delivery_attempts * 0.1))
        
        return cost
    
    def log_delivery_attempt(self, success=True, error_message=None):
        """Log delivery attempt"""
        self.delivery_attempts += 1
        self.last_delivery_attempt = timezone.now()
        
        if success:
            self.mark_as_sent(save=False)
        else:
            self.delivery_error = error_message
            if self.delivery_attempts >= self.max_retries:
                self.status = 'failed'
        
        self.save()
    
    def generate_preview(self):
        """Generate preview of notification"""
        preview = {
            'title': self.title,
            'message': self.message[:100] + '...' if len(self.message) > 100 else self.message,
            'type': self.get_notification_type_display(),
            'priority': self.get_priority_display(),
            'channel': self.get_channel_display(),
            'status': self.get_status_display(),
            'icon': self.get_icon_url(),
            'action': self.action_text,
            'age': self.get_formatted_age(),
            'read': self.is_read,
            'pinned': self.is_pinned,
            'archived': self.is_archived,
        }
        
        if self.image_url:
            preview['image'] = self.image_url
        
        if self.deep_link:
            preview['deep_link'] = self.deep_link
        
        return preview
    
    def get_analytics_summary(self):
        """Get analytics summary"""
        return {
            'impressions': self.impression_count,
            'views': self.view_count,
            'clicks': self.click_count,
            'open_rate': round(self.open_rate, 2),
            'click_through_rate': round(self.click_through_rate, 2),
            'conversion_rate': round(self.conversion_rate, 2),
            'engagement_score': round(self.engagement_score, 2),
            'delivery_attempts': self.delivery_attempts,
            'cost': float(self.cost),
            'cost_currency': self.cost_currency,
        }
    
    def is_urgent(self):
        """Check if notification is urgent"""
        return self.priority in ['urgent', 'critical']
    
    def is_high_priority(self):
        """Check if notification is high priority"""
        return self.priority in ['high', 'urgent', 'critical']
    
    def requires_immediate_attention(self):
        """Check if notification requires immediate attention"""
        if self.is_urgent():
            return True
        
        # Check for security alerts
        if self.notification_type in [
            'security_alert',
            'fraud_detected',
            'suspicious_activity',
            'login_new_device',
            'login_new_location',
        ]:
            return True
        
        # Check for financial alerts
        if self.notification_type in [
            'payment_failed',
            'withdrawal_failed',
            'chargeback',
            'low_balance',
        ]:
            return True
        
        return False
    
    def can_be_scheduled(self):
        """Check if notification can be scheduled"""
        return self.status in ['draft', 'scheduled']
    
    def can_be_cancelled(self):
        """Check if notification can be cancelled"""
        return self.status in ['draft', 'scheduled', 'pending']
    
    def can_be_edited(self):
        """Check if notification can be edited"""
        return self.status in ['draft', 'scheduled']
    
    def schedule(self, scheduled_time, save=True):
        """Schedule notification for future delivery"""
        if not self.can_be_scheduled():
            raise ValidationError("Cannot schedule notification in current status")
        
        self.scheduled_for = scheduled_time
        self.status = 'scheduled'
        
        if save:
            self.save()
    
    def cancel(self, save=True):
        """Cancel scheduled notification"""
        if not self.can_be_cancelled():
            raise ValidationError("Cannot cancel notification in current status")
        
        self.status = 'cancelled'
        self.scheduled_for = None
        
        if save:
            self.save()
    
    def reschedule(self, new_time, save=True):
        """Reschedule notification"""
        self.cancel(save=False)
        self.schedule(new_time, save=save)
    
    def trigger_immediate_delivery(self, save=True):
        """Trigger immediate delivery"""
        if self.scheduled_for:
            self.scheduled_for = None
        
        if self.status in ['draft', 'scheduled']:
            self.status = 'pending'
        
        if save:
            self.save()
    
    def get_scheduled_delay(self):
        """Get delay until scheduled delivery"""
        if self.scheduled_for:
            delay = self.scheduled_for - timezone.now()
            if delay.total_seconds() > 0:
                return delay
        return None
    
    def is_overdue(self):
        """Check if scheduled notification is overdue"""
        if self.scheduled_for and self.status == 'scheduled':
            return timezone.now() > self.scheduled_for
        return False
    
    def process_overdue(self):
        """Process overdue scheduled notification"""
        if self.is_overdue():
            self.status = 'pending'
            self.scheduled_for = None
            self.save()
            return True
        return False
    
    @classmethod
    def get_user_notifications(cls, user, filters=None, order_by='-created_at', limit=50, offset=0):
        """Get notifications for user with filters"""
        queryset = cls.objects.filter(user=user, is_deleted=False)
        
        if filters:
            if filters.get('is_read') is not None:
                queryset = queryset.filter(is_read=filters['is_read'])
            
            if filters.get('notification_type'):
                queryset = queryset.filter(notification_type=filters['notification_type'])
            
            if filters.get('priority'):
                queryset = queryset.filter(priority=filters['priority'])
            
            if filters.get('channel'):
                queryset = queryset.filter(channel=filters['channel'])
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('is_archived') is not None:
                queryset = queryset.filter(is_archived=filters['is_archived'])
            
            if filters.get('is_pinned') is not None:
                queryset = queryset.filter(is_pinned=filters['is_pinned'])
            
            if filters.get('start_date'):
                queryset = queryset.filter(created_at__gte=filters['start_date'])
            
            if filters.get('end_date'):
                queryset = queryset.filter(created_at__lte=filters['end_date'])
            
            if filters.get('search'):
                search_term = filters['search']
                queryset = queryset.filter(
                    Q(title__icontains=search_term) |
                    Q(message__icontains=search_term)
                )
            
            if filters.get('tags'):
                tags = filters['tags']
                if isinstance(tags, list):
                    for tag in tags:
                        queryset = queryset.filter(tags__contains=[tag])
        
        # Hide expired notifications unless explicitly requested
        if not filters or not filters.get('include_expired'):
            queryset = queryset.filter(
                Q(expire_date__isnull=True) |
                Q(expire_date__gt=timezone.now())
            )
        
        # Apply ordering
        if order_by:
            queryset = queryset.order_by(order_by)
        
        # Apply pagination
        if limit:
            queryset = queryset[offset:offset + limit]
        
        return queryset
    
    @classmethod
    def get_unread_count(cls, user):
        """Get count of unread notifications for user"""
        return cls.objects.filter(
            user=user,
            is_read=False,
            is_deleted=False,
            is_archived=False
        ).exclude(
            Q(expire_date__isnull=False) & Q(expire_date__lt=timezone.now())
        ).count()
    
    @classmethod
    def mark_all_as_read(cls, user):
        """Mark all notifications as read for user"""
        updated = cls.objects.filter(
            user=user,
            is_read=False,
            is_deleted=False
        ).update(
            is_read=True,
            read_at=timezone.now(),
            status='read'
        )
        return updated
    
    @classmethod
    def delete_expired(cls):
        """Delete expired notifications"""
        expired = cls.objects.filter(
            Q(expire_date__isnull=False) & Q(expire_date__lt=timezone.now()) |
            Q(auto_delete_after_read=True) & Q(is_read=True) |
            Q(auto_delete_after_days__gt=0) &
            Q(created_at__lt=timezone.now() - timedelta(days=models.F('auto_delete_after_days')))
        )
        count = expired.count()
        expired.delete()
        return count
    
    @classmethod
    def cleanup_old_notifications(cls, days=90):
        """Cleanup old notifications"""
        cutoff_date = timezone.now() - timedelta(days=days)
        old_notifications = cls.objects.filter(
            created_at__lt=cutoff_date,
            is_archived=False,
            is_pinned=False
        )
        count = old_notifications.count()
        old_notifications.delete()
        return count
    
    @classmethod
    def get_stats(cls, user=None, start_date=None, end_date=None):
        """Get notification statistics"""
        queryset = cls.objects.filter(is_deleted=False)
        
        if user:
            queryset = queryset.filter(user=user)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        stats = {
            'total': queryset.count(),
            'read': queryset.filter(is_read=True).count(),
            'unread': queryset.filter(is_read=False).count(),
            'delivered': queryset.filter(is_delivered=True).count(),
            'failed': queryset.filter(status='failed').count(),
            'pending': queryset.filter(status='pending').count(),
            'sent': queryset.filter(status='sent').count(),
            'scheduled': queryset.filter(status='scheduled').count(),
            'by_type': list(queryset.values('notification_type').annotate(
                count=Count('id')
            ).order_by('-count')),
            'by_channel': list(queryset.values('channel').annotate(
                count=Count('id')
            ).order_by('-count')),
            'by_priority': list(queryset.values('priority').annotate(
                count=Count('id')
            ).order_by('-count')),
            'by_status': list(queryset.values('status').annotate(
                count=Count('id')
            ).order_by('-count')),
            'daily_count': list(queryset.annotate(date=TruncDate('created_at')).values('date').annotate(
                count=Count('id')
            ).order_by('date')),
            'avg_engagement': queryset.aggregate(
                avg=Avg('engagement_score')
            )['avg'] or 0.0,
            'total_clicks': queryset.aggregate(
                total=Sum('click_count')
            )['total'] or 0,
            'total_views': queryset.aggregate(
                total=Sum('view_count')
            )['total'] or 0,
            'total_impressions': queryset.aggregate(
                total=Sum('impression_count')
            )['total'] or 0,
        }
        
        return stats
    
    @classmethod
    def create_from_template(cls, template_name, user, context=None, **kwargs):
        """Create notification from template"""
        from ._services_core import NotificationTemplateService
        return NotificationTemplateService.create_from_template(
            template_name, user, context, **kwargs
        )
    
    @classmethod
    def send_bulk_notifications(cls, users, title, message, **kwargs):
        """Send bulk notifications to multiple users"""
        from ._services_core import NotificationService
        return NotificationService.send_bulk_notifications(users, title, message, **kwargs)
    
    @classmethod
    def find_duplicates(cls, title, message, user, hours=24):
        """Find duplicate notifications"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return cls.objects.filter(
            user=user,
            title=title,
            message=message,
            created_at__gte=cutoff_time,
            is_deleted=False
        ).exists()


class NotificationTemplate(models.Model):
    """
    Template for creating notifications
    """
    
    # Basic Information
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Template Name')
    
    description = models.TextField(
        blank=True,
        verbose_name='Description'
    )
    
    # Template Type
    template_type = models.CharField(
        max_length=50,
        choices=Notification.NOTIFICATION_TYPES,
        default='general',
        verbose_name='Template Type')
    
    # Content in multiple languages
    title_en = models.CharField(
        max_length=255,
        verbose_name='Title (English, null=True, blank=True)'
    )
    
    title_bn = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Title (Bengali, null=True, blank=True)'
    )
    
    message_en = models.TextField(
        verbose_name='Message (English)'
    )
    
    message_bn = models.TextField(
        blank=True,
        verbose_name='Message (Bengali)'
    )
    
    # Default values
    default_priority = models.CharField(
        max_length=20,
        choices=Notification.PRIORITY_LEVELS,
        default='medium')
    
    default_channel = models.CharField(
        max_length=20,
        choices=Notification.CHANNEL_CHOICES,
        default='in_app')
    
    default_language = models.CharField(
        max_length=10,
        choices=Notification.LANGUAGE_CHOICES,
        default='en')
    
    # Template variables
    variables = models.JSONField(
        default=list,
        help_text='List of template variables with descriptions'
    )
    
    # Sample data for preview
    sample_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Sample data for template preview'
    )
    
    # Visual elements
    icon_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True)
    
    image_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True)
    
    # Action elements
    action_url_template = models.TextField(
        blank=True,
        help_text='Template for action URL (can include variables)'
    )
    
    action_text_en = models.CharField(
        max_length=100,
        blank=True)
    
    action_text_bn = models.CharField(
        max_length=100,
        blank=True)
    
    deep_link_template = models.TextField(
        blank=True,
        help_text='Template for deep link'
    )
    
    # Metadata template
    metadata_template = models.JSONField(
        default=dict,
        blank=True,
        help_text='Template for metadata'
    )
    
    # Category and tags
    category = models.CharField(
        max_length=50,
        choices=[
            ('system', 'System'),
            ('financial', 'Financial'),
            ('task', 'Task'),
            ('security', 'Security'),
            ('marketing', 'Marketing'),
            ('social', 'Social'),
            ('support', 'Support'),
            ('achievement', 'Achievement'),
            ('gamification', 'Gamification'),
            ('admin', 'Admin'),
        ],
        default='general'
    )
    
    tags = models.JSONField(
        default=list,
        blank=True
    )
    
    # Status and visibility
    is_active = models.BooleanField(
        default=True
    )
    
    is_public = models.BooleanField(
        default=False,
        help_text='Whether template can be used by all users'
    )
    
    # Access control
    allowed_groups = models.JSONField(
        default=list,
        blank=True,
        help_text='User groups allowed to use this template'
    )
    
    allowed_roles = models.JSONField(
        default=list,
        blank=True,
        help_text='User roles allowed to use this template'
    )
    
    # Usage tracking
    usage_count = models.PositiveIntegerField(
        default=0
    )
    
    last_used = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Versioning
    version = models.PositiveIntegerField(
        default=1
    )
    
    parent_template = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_templates')
    
    # Audit fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates')
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_templates')
    
    class Meta:
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['template_type']),
            models.Index(fields=['category']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} (v{self.version})"
    
    def get_title(self, language='en'):
        """Get title in specified language"""
        if language == 'bn' and self.title_bn:
            return self.title_bn
        return self.title_en
    
    def get_message(self, language='en'):
        """Get message in specified language"""
        if language == 'bn' and self.message_bn:
            return self.message_bn
        return self.message_en
    
    def get_action_text(self, language='en'):
        """Get action text in specified language"""
        if language == 'bn' and self.action_text_bn:
            return self.action_text_bn
        return self.action_text_en
    
    def render(self, context=None, language='en'):
        """Render template with context"""
        if context is None:
            context = {}
        
        from .utils import TemplateRenderer
        return TemplateRenderer.render_template(self, context, language)
    
    def create_notification(self, user, context=None, **kwargs):
        """Create notification from template"""
        from ._services_core import NotificationTemplateService
        return NotificationTemplateService.create_from_template(
            self.name, user, context, **kwargs
        )
    
    def increment_usage(self):
        """Increment usage count"""
        self.usage_count += 1
        self.last_used = timezone.now()
        self.save()
    
    def clone(self, new_name=None, **kwargs):
        """Clone template"""
        clone_fields = [
            'description', 'template_type', 'title_en', 'title_bn',
            'message_en', 'message_bn', 'default_priority', 'default_channel',
            'default_language', 'variables', 'sample_data', 'icon_url',
            'image_url', 'action_url_template', 'action_text_en',
            'action_text_bn', 'deep_link_template', 'metadata_template',
            'category', 'tags', 'allowed_groups', 'allowed_roles',
        ]
        
        clone_data = {}
        for field in clone_fields:
            clone_data[field] = getattr(self, field)
        
        # Update with kwargs
        clone_data.update(kwargs)
        
        # Set name
        if new_name:
            clone_data['name'] = new_name
        else:
            clone_data['name'] = f"{self.name} (Copy)"
        
        # Create clone
        clone = NotificationTemplate.objects.create(
            **clone_data,
            created_by=self.created_by,
            parent_template=self,
            version=1
        )
        
        return clone
    
    def validate_variables(self, context):
        """Validate context variables"""
        missing_vars = []
        for var in self.variables:
            if var.get('required', False) and var['name'] not in context:
                missing_vars.append(var['name'])
        
        if missing_vars:
            raise ValidationError(
                f"Missing required variables: {', '.join(missing_vars)}"
            )
        
        return True
    
    def get_preview(self, language='en'):
        """Get template preview"""
        return {
            'name': self.name,
            'type': self.template_type,
            'category': self.category,
            'title': self.get_title(language),
            'message': self.get_message(language),
            'action_text': self.get_action_text(language),
            'icon': self.icon_url,
            'image': self.image_url,
            'variables': self.variables,
            'sample_data': self.sample_data,
        }


class NotificationPreference(models.Model):
    """
    User preferences for notifications
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences')
    
    # Channel preferences
    enable_in_app = models.BooleanField(default=True)
    enable_push = models.BooleanField(default=True)
    enable_email = models.BooleanField(default=False)
    enable_sms = models.BooleanField(default=False)
    enable_telegram = models.BooleanField(default=False)
    enable_whatsapp = models.BooleanField(default=False)
    enable_browser = models.BooleanField(default=True)
    
    # Type preferences
    enable_system_notifications = models.BooleanField(default=True)
    enable_financial_notifications = models.BooleanField(default=True)
    enable_task_notifications = models.BooleanField(default=True)
    enable_security_notifications = models.BooleanField(default=True)
    enable_marketing_notifications = models.BooleanField(default=True)
    enable_social_notifications = models.BooleanField(default=True)
    enable_support_notifications = models.BooleanField(default=True)
    enable_achievement_notifications = models.BooleanField(default=True)
    enable_gamification_notifications = models.BooleanField(default=True)
    
    # Priority preferences
    enable_lowest_priority = models.BooleanField(default=True)
    enable_low_priority = models.BooleanField(default=True)
    enable_medium_priority = models.BooleanField(default=True)
    enable_high_priority = models.BooleanField(default=True)
    enable_urgent_priority = models.BooleanField(default=True)
    enable_critical_priority = models.BooleanField(default=True)
    
    # Notification settings
    sound_enabled = models.BooleanField(default=True)
    vibration_enabled = models.BooleanField(default=True)
    led_enabled = models.BooleanField(default=True)
    badge_enabled = models.BooleanField(default=True)
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    
    # Do not disturb
    do_not_disturb = models.BooleanField(default=False)
    do_not_disturb_until = models.DateTimeField(null=True, blank=True)
    
    # Language preference
    preferred_language = models.CharField(
        max_length=10,
        choices=Notification.LANGUAGE_CHOICES,
        default='en')
    
    # Delivery preferences
    prefer_in_app = models.BooleanField(default=True)
    group_notifications = models.BooleanField(default=True)
    show_previews = models.BooleanField(default=True)
    
    # Auto-cleanup
    auto_delete_read = models.BooleanField(default=False)
    auto_delete_after_days = models.PositiveIntegerField(default=30)
    
    # Notification limits
    max_notifications_per_day = models.PositiveIntegerField(default=50)
    max_push_per_day = models.PositiveIntegerField(default=10)
    max_email_per_day = models.PositiveIntegerField(default=5)
    max_sms_per_day = models.PositiveIntegerField(default=2)
    
    # Analytics
    total_notifications_received = models.PositiveIntegerField(default=0)
    total_notifications_read = models.PositiveIntegerField(default=0)
    total_notifications_clicked = models.PositiveIntegerField(default=0)
    
    average_open_time = models.FloatField(default=0.0)  # in seconds
    average_click_time = models.FloatField(default=0.0)  # in seconds
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Preferences - {self.user.username}"
    
    def is_channel_enabled(self, channel):
        """Check if channel is enabled"""
        channel_map = {
            'in_app': self.enable_in_app,
            'push': self.enable_push,
            'email': self.enable_email,
            'sms': self.enable_sms,
            'telegram': self.enable_telegram,
            'whatsapp': self.enable_whatsapp,
            'browser': self.enable_browser,
        }
        return channel_map.get(channel, False)
    
    def is_type_enabled(self, notification_type):
        """Check if notification type is enabled"""
        # Map notification types to categories
        type_categories = {
            # System
            'system_update': 'system',
            'maintenance': 'system',
            'app_update': 'system',
            'new_feature': 'system',
            'bug_fix': 'system',
            'announcement': 'system',
            'news': 'system',
            
            # Financial
            'payment_success': 'financial',
            'payment_failed': 'financial',
            'withdrawal_success': 'financial',
            'withdrawal_failed': 'financial',
            'withdrawal_pending': 'financial',
            'withdrawal_approved': 'financial',
            'withdrawal_rejected': 'financial',
            'deposit_success': 'financial',
            'deposit_failed': 'financial',
            'refund': 'financial',
            'chargeback': 'financial',
            'subscription_renewal': 'financial',
            'subscription_expired': 'financial',
            'wallet_credited': 'financial',
            'wallet_debited': 'financial',
            'low_balance': 'financial',
            'bonus_added': 'financial',
            'cashback': 'financial',
            'reward_points': 'financial',
            
            # Task
            'task_assigned': 'task',
            'task_completed': 'task',
            'task_rejected': 'task',
            'task_approved': 'task',
            'task_expired': 'task',
            'task_reminder': 'task',
            'task_deadline': 'task',
            'task_reward': 'task',
            'task_verification': 'task',
            'task_dispute': 'task',
            'task_available': 'task',
            'task_limit_reached': 'task',
            
            # Security
            'login_success': 'security',
            'login_failed': 'security',
            'login_new_device': 'security',
            'login_new_location': 'security',
            'password_changed': 'security',
            'password_reset': 'security',
            'two_factor_enabled': 'security',
            'two_factor_disabled': 'security',
            'suspicious_activity': 'security',
            'account_locked': 'security',
            'account_unlocked': 'security',
            'email_verified': 'security',
            'phone_verified': 'security',
            'kyc_approved': 'security',
            'kyc_rejected': 'security',
            'kyc_pending': 'security',
            'kyc_submitted': 'security',
            'fraud_detected': 'security',
            'security_alert': 'security',
            
            # Marketing
            'promotion': 'marketing',
            'offer': 'marketing',
            'discount': 'marketing',
            'coupon': 'marketing',
            'sale': 'marketing',
            'flash_sale': 'marketing',
            'new_arrival': 'marketing',
            'restock': 'marketing',
            'price_drop': 'marketing',
            'abandoned_cart': 'marketing',
            'wishlist': 'marketing',
            'product_review': 'marketing',
            'survey': 'marketing',
            'feedback': 'marketing',
            
            # Social
            'friend_request': 'social',
            'friend_accepted': 'social',
            'friend_rejected': 'social',
            'follow': 'social',
            'unfollow': 'social',
            'message': 'social',
            'comment': 'social',
            'like': 'social',
            'share': 'social',
            'mention': 'social',
            'tag': 'social',
            'invite': 'social',
            'group_invite': 'social',
            'group_join': 'social',
            'group_leave': 'social',
            'event_invite': 'social',
            'event_reminder': 'social',
            
            # Support
            'ticket_created': 'support',
            'ticket_updated': 'support',
            'ticket_resolved': 'support',
            'ticket_closed': 'support',
            'ticket_reply': 'support',
            'ticket_escalated': 'support',
            'live_chat': 'support',
            'chat_message': 'support',
            'chat_request': 'support',
            'faq_suggestion': 'support',
            
            # Achievement
            'level_up': 'achievement',
            'badge_earned': 'achievement',
            'achievement_unlocked': 'achievement',
            'milestone_reached': 'achievement',
            'rank_up': 'achievement',
            'streak': 'achievement',
            'daily_streak': 'achievement',
            'weekly_streak': 'achievement',
            'monthly_streak': 'achievement',
            'challenge_completed': 'achievement',
            'contest_won': 'achievement',
            'contest_participation': 'achievement',
            
            # Gamification
            'daily_reward': 'gamification',
            'weekly_reward': 'gamification',
            'monthly_reward': 'gamification',
            'spin_wheel': 'gamification',
            'scratch_card': 'gamification',
            'lucky_draw': 'gamification',
            'quiz_completed': 'gamification',
            'trivia_winner': 'gamification',
            'mini_game': 'gamification',
        }
        
        category = type_categories.get(notification_type, 'general')
        
        category_map = {
            'system': self.enable_system_notifications,
            'financial': self.enable_financial_notifications,
            'task': self.enable_task_notifications,
            'security': self.enable_security_notifications,
            'marketing': self.enable_marketing_notifications,
            'social': self.enable_social_notifications,
            'support': self.enable_support_notifications,
            'achievement': self.enable_achievement_notifications,
            'gamification': self.enable_gamification_notifications,
        }
        
        return category_map.get(category, True)
    
    def is_priority_enabled(self, priority):
        """Check if priority is enabled"""
        priority_map = {
            'lowest': self.enable_lowest_priority,
            'low': self.enable_low_priority,
            'medium': self.enable_medium_priority,
            'high': self.enable_high_priority,
            'urgent': self.enable_urgent_priority,
            'critical': self.enable_critical_priority,
        }
        return priority_map.get(priority, True)
    
    def is_in_quiet_hours(self):
        """Check if currently in quiet hours"""
        if not self.quiet_hours_enabled or not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        now = timezone.now().time()
        
        if self.quiet_hours_start <= self.quiet_hours_end:
            return self.quiet_hours_start <= now <= self.quiet_hours_end
        else:
            return now >= self.quiet_hours_start or now <= self.quiet_hours_end
    
    def is_in_do_not_disturb(self):
        """Check if do not disturb is active"""
        if not self.do_not_disturb:
            return False
        
        if self.do_not_disturb_until:
            return timezone.now() < self.do_not_disturb_until
        
        return True
    
    def can_receive_notification(self, notification_type, channel, priority):
        """Check if user can receive notification"""
        # Check do not disturb
        if self.is_in_do_not_disturb():
            return False
        
        # Check quiet hours (for non-urgent notifications)
        if not priority in ['urgent', 'critical'] and self.is_in_quiet_hours():
            return False
        
        # Check channel preference
        if not self.is_channel_enabled(channel):
            return False
        
        # Check type preference
        if not self.is_type_enabled(notification_type):
            return False
        
        # Check priority preference
        if not self.is_priority_enabled(priority):
            return False
        
        # Check daily limits
        if not self.check_daily_limit(channel):
            return False
        
        return True
    
    def check_daily_limit(self, channel):
        """Check daily limit for channel"""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        today = timezone.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # Get today's count for channel
        today_count = Notification.objects.filter(
            user=self.user,
            channel=channel,
            created_at__range=[today_start, today_end]
        ).count()
        
        # Check against limit
        limit_map = {
            'push': self.max_push_per_day,
            'email': self.max_email_per_day,
            'sms': self.max_sms_per_day,
        }
        
        limit = limit_map.get(channel, 1000)  # Default high limit
        return today_count < limit
    
    def update_analytics(self, notification):
        """Update analytics based on notification"""
        self.total_notifications_received += 1
        
        if notification.is_read:
            self.total_notifications_read += 1
            
            # Calculate average open time
            if notification.sent_at and notification.read_at:
                open_time = (notification.read_at - notification.sent_at).total_seconds()
                # Update average using moving average
                if self.average_open_time == 0:
                    self.average_open_time = open_time
                else:
                    self.average_open_time = (self.average_open_time + open_time) / 2
        
        if notification.click_count > 0:
            self.total_notifications_clicked += 1
            
            # Calculate average click time
            if notification.read_at:
                # Assuming click happens shortly after read
                click_time = 5.0  # Default assumption
                # Update average using moving average
                if self.average_click_time == 0:
                    self.average_click_time = click_time
                else:
                    self.average_click_time = (self.average_click_time + click_time) / 2
        
        self.save()
    
    def get_stats(self):
        """Get user notification statistics"""
        return {
            'total_received': self.total_notifications_received,
            'total_read': self.total_notifications_read,
            'total_clicked': self.total_notifications_clicked,
            'read_rate': (
                (self.total_notifications_read / self.total_notifications_received * 100)
                if self.total_notifications_received > 0 else 0
            ),
            'click_rate': (
                (self.total_notifications_clicked / self.total_notifications_received * 100)
                if self.total_notifications_received > 0 else 0
            ),
            'average_open_time': self.average_open_time,
            'average_click_time': self.average_click_time,
        }


class DeviceToken(models.Model):
    """
    Device tokens for push notifications
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_tokens')
    
    token = models.CharField(
        max_length=500,
        unique=True)
    
    device_type = models.CharField(
        max_length=50,
        choices=Notification.DEVICE_TYPES)
    
    platform = models.CharField(
        max_length=50,
        choices=Notification.PLATFORM_CHOICES)
    
    app_version = models.CharField(
        max_length=20,
        blank=True)
    
    os_version = models.CharField(
        max_length=20,
        blank=True)
    
    device_model = models.CharField(
        max_length=100,
        blank=True)
    
    device_name = models.CharField(
        max_length=100,
        blank=True)
    
    manufacturer = models.CharField(
        max_length=100,
        blank=True)
    
    # Push service specific
    fcm_token = models.CharField(
        max_length=500,
        blank=True)
    
    apns_token = models.CharField(
        max_length=500,
        blank=True)
    
    web_push_token = models.JSONField(
        default=dict,
        blank=True
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    last_active = models.DateTimeField(auto_now=True)
    
    # Location
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    
    country = models.CharField(
        max_length=100,
        blank=True)
    
    city = models.CharField(
        max_length=100,
        blank=True)
    
    timezone = models.CharField(
        max_length=50,
        blank=True)
    
    language = models.CharField(
        max_length=10,
        choices=Notification.LANGUAGE_CHOICES,
        default='en')
    
    # Settings
    push_enabled = models.BooleanField(default=True)
    
    sound_enabled = models.BooleanField(default=True)
    
    vibration_enabled = models.BooleanField(default=True)
    
    # Statistics
    push_sent = models.PositiveIntegerField(default=0)
    
    push_delivered = models.PositiveIntegerField(default=0)
    
    push_failed = models.PositiveIntegerField(default=0)
    
    last_push_sent = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Device Token'
        verbose_name_plural = 'Device Tokens'
        unique_together = ['user', 'token']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['device_type']),
            models.Index(fields=['platform']),
            models.Index(fields=['last_active']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.device_type} ({self.device_model})"
    
    def get_push_token(self):
        """Get appropriate push token based on platform"""
        if self.platform in ['android_app', 'ios_app']:
            if self.device_type == 'android':
                return self.fcm_token
            elif self.device_type == 'ios':
                return self.apns_token
        elif self.platform == 'progressive_web_app':
            return self.web_push_token
        
        return self.token
    
    def increment_push_sent(self):
        """Increment push sent count"""
        self.push_sent += 1
        self.last_push_sent = timezone.now()
        self.save()
    
    def increment_push_delivered(self):
        """Increment push delivered count"""
        self.push_delivered += 1
        self.save()
    
    def increment_push_failed(self):
        """Increment push failed count"""
        self.push_failed += 1
        self.save()
    
    def get_delivery_rate(self):
        """Get delivery rate"""
        if self.push_sent == 0:
            return 0.0
        return (self.push_delivered / self.push_sent) * 100
    
    def deactivate(self):
        """Deactivate device token"""
        self.is_active = False
        self.save()
    
    def activate(self):
        """Activate device token"""
        self.is_active = True
        self.save()
    
    def update_last_active(self):
        """Update last active timestamp"""
        self.last_active = timezone.now()
        self.save()



class NotificationAnalytics(models.Model):
    """
    Analytics data for notifications
    """
    
    date = models.DateField()
    
    # Counts
    total_notifications = models.PositiveIntegerField(default=0)
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    total_read = models.PositiveIntegerField(default=0)
    total_clicked = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    
    # Rates
    delivery_rate = models.FloatField(default=0.0)
    open_rate = models.FloatField(default=0.0)
    click_through_rate = models.FloatField(default=0.0)
    
    # By Type
    by_type = models.JSONField(default=dict)
    
    # By Channel
    by_channel = models.JSONField(default=dict)
    
    # By Priority
    by_priority = models.JSONField(default=dict)
    
    # User Engagement
    active_users = models.PositiveIntegerField(default=0)
    engaged_users = models.PositiveIntegerField(default=0)
    average_notifications_per_user = models.FloatField(default=0.0)
    
    # Cost
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.00)
    
    average_cost_per_notification = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Notification Analytics'
        verbose_name_plural = 'Notification Analytics'
        unique_together = ['date']
        ordering = ['-date']
    
    def __str__(self):
        return f"Analytics - {self.date}"
    
    @classmethod
    def generate_daily_report(cls, date=None):
        """Generate daily analytics report"""
        if date is None:
            date = timezone.now().date()
        
        # Get data for the date
        start_datetime = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.min.time()))
        end_datetime = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.max.time()))
        
        notifications = Notification.objects.filter(
            created_at__range=[start_datetime, end_datetime],
            is_deleted=False
        )
        
        total_count = notifications.count()
        
        if total_count == 0:
            return None
        
        # Calculate basic stats
        sent_count = notifications.filter(is_sent=True).count()
        delivered_count = notifications.filter(is_delivered=True).count()
        read_count = notifications.filter(is_read=True).count()
        failed_count = notifications.filter(status='failed').count()
        
        click_count = notifications.aggregate(
            total=Sum('click_count')
        )['total'] or 0
        
        # Calculate by type
        by_type = {}
        for notification in notifications.values('notification_type').annotate(
            count=Count('id')
        ):
            by_type[notification['notification_type']] = notification['count']
        
        # Calculate by channel
        by_channel = {}
        for notification in notifications.values('channel').annotate(
            count=Count('id')
        ):
            by_channel[notification['channel']] = notification['count']
        
        # Calculate by priority
        by_priority = {}
        for notification in notifications.values('priority').annotate(
            count=Count('id')
        ):
            by_priority[notification['priority']] = notification['count']
        
        # Calculate user stats
        user_ids = notifications.values('user').distinct().count()
        
        # Calculate cost
        cost_data = notifications.aggregate(
            total=Sum('cost'),
            average=Avg('cost')
        )
        
        total_cost = cost_data['total'] or 0
        average_cost = cost_data['average'] or 0
        
        # Create or update analytics record
        analytics, created = cls.objects.update_or_create(
            date=date,
            defaults={
                'total_notifications': total_count,
                'total_sent': sent_count,
                'total_delivered': delivered_count,
                'total_read': read_count,
                'total_clicked': click_count,
                'total_failed': failed_count,
                'delivery_rate': (delivered_count / sent_count * 100) if sent_count > 0 else 0,
                'open_rate': (read_count / sent_count * 100) if sent_count > 0 else 0,
                'click_through_rate': (click_count / sent_count * 100) if sent_count > 0 else 0,
                'by_type': by_type,
                'by_channel': by_channel,
                'by_priority': by_priority,
                'active_users': user_ids,
                'engaged_users': read_count,  # Simplified
                'average_notifications_per_user': total_count / user_ids if user_ids > 0 else 0,
                'total_cost': total_cost,
                'average_cost_per_notification': average_cost,
            }
        )
        
        return analytics
    
    def get_summary(self):
        """Get analytics summary"""
        return {
            'date': self.date,
            'total_notifications': self.total_notifications,
            'total_sent': self.total_sent,
            'total_delivered': self.total_delivered,
            'total_read': self.total_read,
            'total_clicked': self.total_clicked,
            'total_failed': self.total_failed,
            'delivery_rate': round(self.delivery_rate, 2),
            'open_rate': round(self.open_rate, 2),
            'click_through_rate': round(self.click_through_rate, 2),
            'active_users': self.active_users,
            'engaged_users': self.engaged_users,
            'average_notifications_per_user': round(self.average_notifications_per_user, 2),
            'total_cost': float(self.total_cost),
            'average_cost_per_notification': float(self.average_cost_per_notification),
        }


class NotificationRule(models.Model):
    """
    Rules for automated notifications
    """
    
    name = models.CharField(max_length=255, null=True, blank=True)
    
    description = models.TextField(blank=True)
    
    # Trigger
    trigger_type = models.CharField(
        max_length=50,
        choices=[
            ('event', 'Event'),
            ('schedule', 'Schedule'),
            ('condition', 'Condition'),
            ('webhook', 'Webhook'),
        ]
    )
    
    trigger_config = models.JSONField(default=dict)
    
    # Conditions
    conditions = models.JSONField(default=list)
    
    # Action
    action_type = models.CharField(
        max_length=50,
        choices=[
            ('send_notification', 'Send Notification'),
            ('update_notification', 'Update Notification'),
            ('delete_notification', 'Delete Notification'),
            ('archive_notification', 'Archive Notification'),
            ('send_email', 'Send Email'),
            ('call_webhook', 'Call Webhook'),
        ],
        default='send_notification'
    )
    
    action_config = models.JSONField(default=dict)
    
    # Target
    target_type = models.CharField(
        max_length=50,
        choices=[
            ('user', 'Specific User'),
            ('user_group', 'User Group'),
            ('all_users', 'All Users'),
            ('dynamic', 'Dynamic'),
        ]
    )
    
    target_config = models.JSONField(default=dict)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    is_enabled = models.BooleanField(default=True)
    
    # Execution
    last_triggered = models.DateTimeField(null=True, blank=True)
    
    trigger_count = models.PositiveIntegerField(default=0)
    
    success_count = models.PositiveIntegerField(default=0)
    
    failure_count = models.PositiveIntegerField(default=0)
    
    # Limits
    max_executions = models.PositiveIntegerField(null=True, blank=True)
    
    execution_interval = models.PositiveIntegerField(
        default=0,
        help_text='Minimum seconds between executions (0 = no limit)'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True)
    
    class Meta:
        verbose_name = 'Notification Rule'
        verbose_name_plural = 'Notification Rules'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_trigger_type_display()})"
    
    def can_execute(self):
        """Check if rule can execute"""
        if not self.is_active or not self.is_enabled:
            return False
        
        if self.max_executions and self.trigger_count >= self.max_executions:
            return False
        
        if self.execution_interval > 0 and self.last_triggered:
            next_execution_time = self.last_triggered + timedelta(seconds=self.execution_interval)
            if timezone.now() < next_execution_time:
                return False
        
        return True
    
    def execute(self, context=None):
        """Execute rule"""
        if not self.can_execute():
            return False
        
        self.trigger_count += 1
        self.last_triggered = timezone.now()
        
        try:
            from ._services_core import NotificationRuleService
            result = NotificationRuleService.execute_rule(self, context)
            
            if result:
                self.success_count += 1
            else:
                self.failure_count += 1
            
            self.save()
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.save()
            raise e
    
    def evaluate_conditions(self, context):
        """Evaluate rule conditions"""
        if not self.conditions:
            return True
        
        from ._services_core import NotificationRuleService
        return NotificationRuleService.evaluate_conditions(self.conditions, context)
    
    def get_target_users(self):
        """Get target users for rule"""
        from ._services_core import NotificationRuleService
        return NotificationRuleService.get_target_users(self)
    
    def test_execution(self, test_context=None):
        """Test rule execution"""
        from ._services_core import NotificationRuleService
        return NotificationRuleService.test_rule(self, test_context)


class NotificationFeedback(models.Model):
    """
    User feedback for notifications
    """
    
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='feedbacks')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_feedbacks')
    
    # Feedback
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    feedback = models.TextField(blank=True)
    
    feedback_type = models.CharField(
        max_length=50,
        choices=[
            ('positive', 'Positive'),
            ('negative', 'Negative'),
            ('neutral', 'Neutral'),
            ('suggestion', 'Suggestion'),
            ('bug_report', 'Bug Report'),
            ('feature_request', 'Feature Request'),
        ]
    )
    
    # Response
    is_helpful = models.BooleanField(null=True, blank=True)
    
    would_like_more = models.BooleanField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Notification Feedback'
        verbose_name_plural = 'Notification Feedbacks'
        unique_together = ['notification', 'user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Feedback for {self.notification.title} by {self.user.username}"
    
    def save(self, *args, **kwargs):
        """Update notification engagement score on feedback"""
        super().save(*args, **kwargs)
        
        # Update notification engagement score
        self.notification.calculate_engagement_score()
        self.notification.save()


class NotificationLog(models.Model):
    """
    Log for notification events
    """
    
    # Log Types
    LOG_TYPES = (
        ('delivery', 'Delivery'),
        ('read', 'Read'),
        ('click', 'Click'),
        ('dismiss', 'Dismiss'),
        ('archive', 'Archive'),
        ('delete', 'Delete'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
        ('debug', 'Debug'),
    )
    
    # Log Levels
    LOG_LEVELS = (
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    )
    
    # Basic Information
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='logs',
        null=True,
        blank=True)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True)
    
    # Log Details
    log_type = models.CharField(
        max_length=50,
        choices=LOG_TYPES)
    
    log_level = models.CharField(
        max_length=20,
        choices=LOG_LEVELS,
        default='info')
    
    message = models.TextField()
    
    details = models.JSONField(
        default=dict,
        blank=True
    )
    
    # Source
    source = models.CharField(
        max_length=100,
        blank=True)
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    
    user_agent = models.TextField(
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['notification']),
            models.Index(fields=['user']),
            models.Index(fields=['log_type']),
            models.Index(fields=['log_level']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_log_type_display()} - {self.message[:50]}"
    
    @classmethod
    def log_delivery(cls, notification, success=True, details=None):
        """Log delivery event"""
        log_type = 'delivery'
        log_level = 'info' if success else 'error'
        message = f"Notification delivered: {notification.title}" if success else f"Notification delivery failed: {notification.title}"
        
        if details is None:
            details = {}
        
        details.update({
            'notification_id': str(notification.id),
            'user_id': notification.user_id,
            'channel': notification.channel,
            'success': success,
        })
        
        return cls.objects.create(
            notification=notification,
            user=notification.user,
            log_type=log_type,
            log_level=log_level,
            message=message,
            details=details
        )
    
    @classmethod
    def log_read(cls, notification):
        """Log read event"""
        return cls.objects.create(
            notification=notification,
            user=notification.user,
            log_type='read',
            message=f"Notification read: {notification.title}",
            details={
                'notification_id': str(notification.id),
                'user_id': notification.user_id,
                'read_at': notification.read_at.isoformat() if notification.read_at else None,
            }
        )
    
    @classmethod
    def log_click(cls, notification):
        """Log click event"""
        return cls.objects.create(
            notification=notification,
            user=notification.user,
            log_type='click',
            message=f"Notification clicked: {notification.title}",
            details={
                'notification_id': str(notification.id),
                'user_id': notification.user_id,
                'click_count': notification.click_count,
                'action_url': notification.action_url,
            }
        )
    
    @classmethod
    def log_error(cls, message, notification=None, user=None, details=None):
        """Log error event"""
        return cls.objects.create(
            notification=notification,
            user=user,
            log_type='error',
            log_level='error',
            message=message,
            details=details or {}
        )
        
        
class Notice(models.Model):
    """
    Notice/Announcement Model for important announcements
    """
    
    # Notice Types
    NOTICE_TYPES = (
        ('announcement', 'Announcement'),
        ('update', 'System Update'),
        ('maintenance', 'Maintenance'),
        ('promotion', 'Promotion'),
        ('warning', 'Warning'),
        ('information', 'Information'),
        ('emergency', 'Emergency'),
        ('holiday', 'Holiday'),
        ('event', 'Event'),
        ('news', 'News'),
    )
    
    # Priority Levels
    PRIORITY_LEVELS = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    # Status Choices
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
        ('expired', 'Expired'),
    )
    
    # Target Audience
    AUDIENCE_CHOICES = (
        ('all', 'All Users'),
        ('specific', 'Specific Users'),
        ('group', 'User Group'),
        ('role', 'User Role'),
        ('premium', 'Premium Users'),
        ('new', 'New Users'),
        ('active', 'Active Users'),
        ('inactive', 'Inactive Users'),
    )
    
    # ==================== CORE FIELDS ====================
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='Notice ID'
    )
    
    title = models.CharField(
        max_length=255,
        verbose_name='Notice Title',
        help_text='Title of the notice')
    
    content = models.TextField(
        verbose_name='Notice Content',
        help_text='Detailed content of the notice'
    )
    
    short_description = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='Short Description',
        help_text='Brief description of the notice')
    
    # ==================== CLASSIFICATION ====================
    
    notice_type = models.CharField(
        max_length=50,
        choices=NOTICE_TYPES,
        default='announcement',
        verbose_name='Notice Type')
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_LEVELS,
        default='medium',
        verbose_name='Priority Level')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='Notice Status')
    
    audience = models.CharField(
        max_length=50,
        choices=AUDIENCE_CHOICES,
        default='all',
        verbose_name='Target Audience')
    
    # ==================== VISIBILITY SETTINGS ====================
    
    is_published = models.BooleanField(
        default=False,
        verbose_name='Is Published',
        help_text='Whether notice is publicly visible'
    )
    
    is_pinned = models.BooleanField(
        default=False,
        verbose_name='Is Pinned',
        help_text='Pin notice to top'
    )
    
    is_popup = models.BooleanField(
        default=False,
        verbose_name='Show as Popup',
        help_text='Show as popup notification'
    )
    
    requires_acknowledgment = models.BooleanField(
        default=False,
        verbose_name='Requires Acknowledgment',
        help_text='User must acknowledge reading'
    )
    
    # ==================== TIMESTAMPS ====================
    
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Published At',
        help_text='When notice was published'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )
    
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Start Date',
        help_text='When notice becomes active'
    )
    
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='End Date',
        help_text='When notice expires'
    )
    
    # ==================== VISUAL ELEMENTS ====================
    
    image = models.ImageField(
        upload_to='notices/',
        null=True,
        blank=True,
        verbose_name='Notice Image'
    )
    
    icon = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Icon Name',
        help_text='FontAwesome or Material icon name')
    
    color = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Accent Color',
        help_text='Hex color code (e.g., #FF0000, null=True, blank=True)'
    )
    
    # ==================== LINKS & ACTIONS ====================
    
    action_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name='Action URL',
        help_text='URL to navigate when clicked')
    
    action_text = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Action Text',
        help_text='Text for action button')
    
    external_link = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name='External Link',
        help_text='External website link')
    
    # ==================== TARGETING ====================
    
    target_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='targeted_notices',
        verbose_name='Target Users',
        help_text='Specific users to show notice'
    )
    
    user_groups = models.JSONField(
        default=list,
        blank=True,
        verbose_name='User Groups',
        help_text='List of user group IDs'
    )
    
    user_roles = models.JSONField(
        default=list,
        blank=True,
        verbose_name='User Roles',
        help_text='List of user roles'
    )
    
    # ==================== METADATA ====================
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata',
        help_text='Additional data in JSON format'
    )
    
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Tags',
        help_text='Tags for categorization'
    )
    
    # ==================== STATISTICS ====================
    
    view_count = models.PositiveIntegerField(
        default=0,
        verbose_name='View Count'
    )
    
    acknowledge_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Acknowledge Count'
    )
    
    click_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Click Count'
    )
    
    # ==================== CREATOR INFO ====================
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_notices',
        verbose_name='Created By')
    
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_notices',
        verbose_name='Updated By')
    
    # ==================== VERSIONING ====================
    
    version = models.PositiveIntegerField(
        default=1,
        verbose_name='Version'
    )
    
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='next_versions',
        verbose_name='Previous Version')
    
    class Meta:
        verbose_name = 'Notice'
        verbose_name_plural = 'Notices'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', 'is_published']),
            models.Index(fields=['notice_type']),
            models.Index(fields=['priority']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['is_pinned']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_notice_type_display()})"
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Validate dates
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError('End date must be after start date')
        
        if self.published_at and self.start_date and self.published_at < self.start_date:
            raise ValidationError('Published date cannot be before start date')
    
    def save(self, *args, **kwargs):
        """Custom save logic"""
        # Set published_at if publishing for first time
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        
        # Set status based on is_published
        if self.is_published:
            self.status = 'published'
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def is_active(self):
        """Check if notice is currently active"""
        now = timezone.now()
        
        if not self.is_published or self.status != 'published':
            return False
        
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        return True
    
    def increment_view_count(self):
        """Increment view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def increment_acknowledge_count(self):
        """Increment acknowledge count"""
        self.acknowledge_count += 1
        self.save(update_fields=['acknowledge_count'])
    
    def increment_click_count(self):
        """Increment click count"""
        self.click_count += 1
        self.save(update_fields=['click_count'])
    
    def publish(self):
        """Publish the notice"""
        self.is_published = True
        self.status = 'published'
        self.published_at = timezone.now()
        self.save()
    
    def unpublish(self):
        """Unpublish the notice"""
        self.is_published = False
        self.status = 'draft'
        self.save()
    
    def archive(self):
        """Archive the notice"""
        self.status = 'archived'
        self.is_published = False
        self.save()
    
    def is_expired(self):
        """Check if notice is expired"""
        if self.end_date and timezone.now() > self.end_date:
            return True
        return False
    
    def should_show_to_user(self, user):
        """Check if notice should be shown to specific user"""
        if not self.is_active():
            return False
        
        # Check audience targeting
        if self.audience == 'all':
            return True
        
        elif self.audience == 'specific':
            return self.target_users.filter(id=user.id).exists()
        
        elif self.audience == 'premium':
            # Assuming user has is_premium field
            return hasattr(user, 'is_premium') and user.is_premium
        
        elif self.audience == 'new':
            # Users registered in last 7 days
            return (timezone.now() - user.date_joined).days <= 7
        
        elif self.audience == 'active':
            # Users active in last 30 days
            if hasattr(user, 'last_login'):
                return user.last_login and (timezone.now() - user.last_login).days <= 30
            return True
        
        return False
    
    def get_days_left(self):
        """Get days left until expiration"""
        if not self.end_date:
            return None
        
        now = timezone.now()
        if now > self.end_date:
            return 0
        
        return (self.end_date - now).days
    
    def get_icon_class(self):
        """Get icon class based on notice type"""
        icon_map = {
            'announcement': 'fa-bullhorn',
            'update': 'fa-sync-alt',
            'maintenance': 'fa-tools',
            'promotion': 'fa-percentage',
            'warning': 'fa-exclamation-triangle',
            'information': 'fa-info-circle',
            'emergency': 'fa-exclamation-circle',
            'holiday': 'fa-gift',
            'event': 'fa-calendar-alt',
            'news': 'fa-newspaper',
        }
        
        return self.icon or icon_map.get(self.notice_type, 'fa-bell')
    
    def get_color_class(self):
        """Get color class based on priority"""
        color_map = {
            'low': 'info',
            'medium': 'primary',
            'high': 'warning',
            'urgent': 'danger',
        }
        
        return self.color or color_map.get(self.priority, 'primary')
    
    def clone(self, new_title=None):
        """Clone notice"""
        clone = Notice.objects.create(
            title=new_title or f"Copy of {self.title}",
            content=self.content,
            short_description=self.short_description,
            notice_type=self.notice_type,
            priority=self.priority,
            status='draft',
            audience=self.audience,
            image=self.image,
            icon=self.icon,
            color=self.color,
            action_url=self.action_url,
            action_text=self.action_text,
            external_link=self.external_link,
            metadata=self.metadata.copy(),
            tags=self.tags.copy(),
            created_by=self.created_by,
            previous_version=self,
            version=self.version + 1,
        )
        
        # Clone target users
        if self.target_users.exists():
            clone.target_users.set(self.target_users.all())
        
        return clone
    
    @classmethod
    def get_active_notices(cls, user=None):
        """Get active notices for user or all"""
        queryset = cls.objects.filter(
            is_published=True,
            status='published'
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=timezone.now())
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
        ).order_by('-priority', '-published_at', '-is_pinned')
        
        if user:
            # Filter by audience targeting
            filtered_notices = []
            for notice in queryset:
                if notice.should_show_to_user(user):
                    filtered_notices.append(notice)
            return filtered_notices
        
        return queryset
    
    @classmethod
    def get_popup_notices(cls, user=None):
        """Get notices that should show as popup"""
        notices = cls.get_active_notices(user)
        return [notice for notice in notices if notice.is_popup]
    
    @classmethod
    def get_pinned_notices(cls, user=None):
        """Get pinned notices"""
        notices = cls.get_active_notices(user)
        return [notice for notice in notices if notice.is_pinned]
    
    @classmethod
    def cleanup_expired_notices(cls):
        """Cleanup expired notices"""
        expired = cls.objects.filter(
            end_date__lt=timezone.now(),
            status='published'
        )
        
        for notice in expired:
            notice.status = 'expired'
            notice.is_published = False
            notice.save()
        
        return expired.count()