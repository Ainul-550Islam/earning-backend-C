# earning_backend/api/notifications/choices.py
"""
Choices — All Django choice tuples for Notification models.

Centralises every (value, label) pair so models.py, serializers.py,
filters.py and admin.py all import from one place.
"""

# ---------------------------------------------------------------------------
# Notification Type choices  (150+ types)
# ---------------------------------------------------------------------------

NOTIFICATION_TYPE_CHOICES = (
    # System
    ('system_update',       'System Update'),
    ('maintenance',         'System Maintenance'),
    ('app_update',          'App Update'),
    ('new_feature',         'New Feature'),
    ('bug_fix',             'Bug Fix'),
    ('announcement',        'Announcement'),
    ('system_alert',        'System Alert'),
    ('downtime_notice',     'Downtime Notice'),

    # Financial
    ('withdrawal_success',  'Withdrawal Successful'),
    ('withdrawal_pending',  'Withdrawal Pending'),
    ('withdrawal_approved', 'Withdrawal Approved'),
    ('withdrawal_rejected', 'Withdrawal Rejected'),
    ('withdrawal_failed',   'Withdrawal Failed'),
    ('deposit_success',     'Deposit Successful'),
    ('deposit_failed',      'Deposit Failed'),
    ('wallet_credited',     'Wallet Credited'),
    ('wallet_debited',      'Wallet Debited'),
    ('low_balance',         'Low Balance Warning'),
    ('bonus_added',         'Bonus Added'),
    ('cashback',            'Cashback Received'),
    ('refund_processed',    'Refund Processed'),
    ('payment_overdue',     'Payment Overdue'),
    ('invoice_generated',   'Invoice Generated'),

    # Task / Offer / Survey
    ('task_assigned',       'Task Assigned'),
    ('task_completed',      'Task Completed'),
    ('task_approved',       'Task Approved'),
    ('task_rejected',       'Task Rejected'),
    ('task_expired',        'Task Expired'),
    ('task_reward',         'Task Reward'),
    ('task_reminder',       'Task Reminder'),
    ('offer_available',     'New Offer Available'),
    ('offer_completed',     'Offer Completed'),
    ('offer_expired',       'Offer Expired'),
    ('survey_available',    'Survey Available'),
    ('survey_completed',    'Survey Completed'),
    ('survey_reward',       'Survey Reward'),
    ('ad_available',        'Ad Available'),
    ('ad_viewed',           'Ad Viewed Reward'),

    # Daily Rewards & Streaks
    ('daily_reward',        'Daily Reward'),
    ('streak_reward',       'Streak Reward'),
    ('streak_broken',       'Streak Broken'),
    ('milestone_reached',   'Milestone Reached'),
    ('spin_reward',         'Spin Wheel Reward'),
    ('lucky_draw',          'Lucky Draw'),

    # Referral
    ('referral_signup',     'Referral Signup'),
    ('referral_completed',  'Referral Completed'),
    ('referral_reward',     'Referral Reward'),
    ('referral_rejected',   'Referral Rejected'),
    ('referral_expired',    'Referral Expired'),
    ('team_bonus',          'Team Bonus'),
    ('affiliate_commission','Affiliate Commission'),
    ('sub_affiliate_earn',  'Sub-Affiliate Earning'),

    # Security / Auth
    ('login_success',       'Login Successful'),
    ('login_failed',        'Login Failed'),
    ('login_new_device',    'New Device Login'),
    ('login_new_location',  'New Location Login'),
    ('logout',              'Logout'),
    ('password_changed',    'Password Changed'),
    ('password_reset',      'Password Reset'),
    ('two_factor_enabled',  '2FA Enabled'),
    ('two_factor_disabled', '2FA Disabled'),
    ('two_factor_code',     '2FA Code Sent'),
    ('suspicious_activity', 'Suspicious Activity'),
    ('account_locked',      'Account Locked'),
    ('account_unlocked',    'Account Unlocked'),
    ('account_suspended',   'Account Suspended'),
    ('account_reinstated',  'Account Reinstated'),
    ('account_warning',     'Account Warning'),
    ('session_expired',     'Session Expired'),

    # KYC
    ('kyc_submitted',       'KYC Submitted'),
    ('kyc_approved',        'KYC Approved'),
    ('kyc_rejected',        'KYC Rejected'),
    ('kyc_expired',         'KYC Expired'),
    ('kyc_resubmit',        'KYC Resubmission Required'),

    # Achievement / Gamification
    ('achievement_unlocked','Achievement Unlocked'),
    ('badge_earned',        'Badge Earned'),
    ('rank_up',             'Rank Increased'),
    ('rank_down',           'Rank Decreased'),
    ('level_up',            'Level Up'),
    ('leaderboard_update',  'Leaderboard Update'),
    ('challenge_completed', 'Challenge Completed'),
    ('tournament_started',  'Tournament Started'),
    ('tournament_ended',    'Tournament Ended'),
    ('tournament_reward',   'Tournament Reward'),

    # Support
    ('ticket_created',      'Support Ticket Created'),
    ('ticket_updated',      'Support Ticket Updated'),
    ('ticket_replied',      'Support Ticket Reply'),
    ('ticket_resolved',     'Support Ticket Resolved'),
    ('ticket_closed',       'Support Ticket Closed'),
    ('feedback_received',   'Feedback Received'),

    # Marketing / Promotions
    ('promotion',           'Promotion'),
    ('flash_sale',          'Flash Sale'),
    ('special_offer',       'Special Offer'),
    ('limited_offer',       'Limited Time Offer'),
    ('vip_offer',           'VIP Offer'),
    ('birthday_bonus',      'Birthday Bonus'),

    # CPAlead / Affiliate
    ('postback_received',   'Postback Received'),
    ('postback_failed',     'Postback Failed'),
    ('conversion_received', 'Conversion Received'),
    ('campaign_live',       'Campaign Live'),
    ('campaign_paused',     'Campaign Paused'),
    ('publisher_payout',    'Publisher Payout'),
    ('advertiser_budget_low','Advertiser Budget Low'),
    ('chargeback_received', 'Chargeback Received'),
    ('ip_fraud_blocked',    'IP/Fraud Blocked'),
    ('fraud_detected',      'Fraud Detected'),
    ('smart_link_click',    'Smart Link Click'),
    ('offer_rejected',      'Offer Rejected'),
)

# ---------------------------------------------------------------------------
# Channel choices
# ---------------------------------------------------------------------------

CHANNEL_CHOICES = (
    ('in_app',    'In-App'),
    ('push',      'Push Notification'),
    ('email',     'Email'),
    ('sms',       'SMS'),
    ('telegram',  'Telegram'),
    ('whatsapp',  'WhatsApp'),
    ('browser',   'Browser Push'),
    ('slack',     'Slack'),
    ('discord',   'Discord'),
    ('all',       'All Channels'),
)

# ---------------------------------------------------------------------------
# Priority choices
# ---------------------------------------------------------------------------

PRIORITY_CHOICES = (
    ('lowest',   'Lowest'),
    ('low',      'Low'),
    ('medium',   'Medium'),
    ('high',     'High'),
    ('urgent',   'Urgent'),
    ('critical', 'Critical'),
)

PRIORITY_SCORE = {
    'lowest': 1, 'low': 2, 'medium': 5,
    'high': 7,  'urgent': 9, 'critical': 10,
}

# ---------------------------------------------------------------------------
# Status choices
# ---------------------------------------------------------------------------

STATUS_CHOICES = (
    ('draft',     'Draft'),
    ('scheduled', 'Scheduled'),
    ('pending',   'Pending'),
    ('sending',   'Sending'),
    ('sent',      'Sent'),
    ('delivered', 'Delivered'),
    ('read',      'Read'),
    ('failed',    'Failed'),
    ('cancelled', 'Cancelled'),
    ('expired',   'Expired'),
)

# ---------------------------------------------------------------------------
# Category choices
# ---------------------------------------------------------------------------

CATEGORY_CHOICES = (
    ('system',       'System'),
    ('financial',    'Financial'),
    ('task_related', 'Task Related'),
    ('security',     'Security'),
    ('marketing',    'Marketing'),
    ('social',       'Social'),
    ('support',      'Support'),
    ('achievement',  'Achievement'),
    ('gamification', 'Gamification'),
    ('admin',        'Admin'),
)

# ---------------------------------------------------------------------------
# Device type choices
# ---------------------------------------------------------------------------

DEVICE_TYPE_CHOICES = (
    ('android', 'Android'),
    ('ios',     'iOS'),
    ('web',     'Web Browser'),
    ('desktop', 'Desktop'),
    ('other',   'Other'),
)

# ---------------------------------------------------------------------------
# Campaign status choices
# ---------------------------------------------------------------------------

CAMPAIGN_STATUS_CHOICES = (
    ('draft',     'Draft'),
    ('scheduled', 'Scheduled'),
    ('running',   'Running'),
    ('paused',    'Paused'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
    ('failed',    'Failed'),
)

# ---------------------------------------------------------------------------
# Target type choices (for campaigns)
# ---------------------------------------------------------------------------

TARGET_TYPE_CHOICES = (
    ('all',        'All Users'),
    ('segment',    'User Segment'),
    ('tier',       'By Membership Tier'),
    ('geo',        'By Geography'),
    ('inactive',   'Inactive Users'),
    ('new',        'New Users'),
    ('high_value', 'High-Value Users'),
    ('custom',     'Custom'),
)

# ---------------------------------------------------------------------------
# Rule trigger choices
# ---------------------------------------------------------------------------

RULE_TRIGGER_CHOICES = (
    ('user_action',      'User Action'),
    ('event',            'System Event'),
    ('scheduled',        'Scheduled'),
    ('threshold',        'Threshold Reached'),
    ('status_change',    'Status Change'),
    ('inactivity',       'User Inactivity'),
    ('birthday',         'Birthday'),
    ('anniversary',      'Anniversary'),
    ('custom',           'Custom Trigger'),
)

# ---------------------------------------------------------------------------
# Rule action choices
# ---------------------------------------------------------------------------

RULE_ACTION_CHOICES = (
    ('send_notification', 'Send Notification'),
    ('send_email',        'Send Email'),
    ('send_sms',          'Send SMS'),
    ('send_push',         'Send Push Notification'),
    ('add_badge',         'Add Badge'),
    ('credit_wallet',     'Credit Wallet'),
    ('custom',            'Custom Action'),
)

# ---------------------------------------------------------------------------
# Feedback type choices
# ---------------------------------------------------------------------------

FEEDBACK_TYPE_CHOICES = (
    ('like',      'Like'),
    ('dislike',   'Dislike'),
    ('report',    'Report'),
    ('dismiss',   'Dismiss'),
    ('helpful',   'Helpful'),
    ('not_relevant', 'Not Relevant'),
)

# ---------------------------------------------------------------------------
# Log level choices
# ---------------------------------------------------------------------------

LOG_LEVEL_CHOICES = (
    ('debug',    'Debug'),
    ('info',     'Info'),
    ('warning',  'Warning'),
    ('error',    'Error'),
    ('critical', 'Critical'),
)

LOG_TYPE_CHOICES = (
    ('sent',      'Sent'),
    ('delivered', 'Delivered'),
    ('read',      'Read'),
    ('failed',    'Failed'),
    ('retry',     'Retry'),
    ('cancelled', 'Cancelled'),
    ('system',    'System'),
)

# ---------------------------------------------------------------------------
# Opt-out reason choices
# ---------------------------------------------------------------------------

OPT_OUT_REASON_CHOICES = (
    ('too_many',      'Too Many Notifications'),
    ('not_relevant',  'Not Relevant'),
    ('privacy',       'Privacy Concern'),
    ('spam',          'Marked as Spam'),
    ('user_request',  'User Request'),
    ('admin_action',  'Admin Action'),
    ('system',        'System / Automatic'),
    ('other',         'Other'),
)

# ---------------------------------------------------------------------------
# Delivery log status choices (channel-specific)
# ---------------------------------------------------------------------------

PUSH_DELIVERY_STATUS_CHOICES = (
    ('pending',       'Pending'),
    ('sent',          'Sent'),
    ('delivered',     'Delivered'),
    ('failed',        'Failed'),
    ('invalid_token', 'Invalid Token'),
    ('rate_limited',  'Rate Limited'),
)

EMAIL_DELIVERY_STATUS_CHOICES = (
    ('pending',       'Pending'),
    ('queued',        'Queued'),
    ('sent',          'Sent'),
    ('delivered',     'Delivered'),
    ('opened',        'Opened'),
    ('clicked',       'Clicked'),
    ('bounced',       'Bounced'),
    ('spam',          'Marked as Spam'),
    ('unsubscribed',  'Unsubscribed'),
    ('failed',        'Failed'),
)

SMS_DELIVERY_STATUS_CHOICES = (
    ('pending',        'Pending'),
    ('queued',         'Queued'),
    ('sent',           'Sent'),
    ('delivered',      'Delivered'),
    ('failed',         'Failed'),
    ('undelivered',    'Undelivered'),
    ('invalid_number', 'Invalid Number'),
)

SMS_GATEWAY_CHOICES = (
    ('twilio',    'Twilio'),
    ('shoho_sms', 'ShohoSMS (Bangladesh)'),
    ('nexmo',     'Vonage / Nexmo'),
    ('aws_sns',   'AWS SNS'),
    ('other',     'Other'),
)

# ---------------------------------------------------------------------------
# In-App message type choices
# ---------------------------------------------------------------------------

IN_APP_MESSAGE_TYPE_CHOICES = (
    ('banner',       'Banner'),
    ('modal',        'Modal'),
    ('toast',        'Toast'),
    ('bottom_sheet', 'Bottom Sheet'),
    ('full_screen',  'Full Screen'),
)

# ---------------------------------------------------------------------------
# Journey status choices
# ---------------------------------------------------------------------------

JOURNEY_STATUS_CHOICES = (
    ('enrolled',   'Enrolled'),
    ('active',     'Active'),
    ('completed',  'Completed'),
    ('exited',     'Exited'),
    ('cancelled',  'Cancelled'),
)

# ---------------------------------------------------------------------------
# Sync strategy choices
# ---------------------------------------------------------------------------

SYNC_STRATEGY_CHOICES = (
    ('latest_wins',    'Latest Wins'),
    ('source_wins',    'Source Wins'),
    ('target_wins',    'Target Wins'),
    ('manual_review',  'Manual Review'),
    ('merge',          'Merge Fields'),
    ('reject',         'Reject Update'),
)

# ---------------------------------------------------------------------------
# Health status choices
# ---------------------------------------------------------------------------

HEALTH_STATUS_CHOICES = (
    ('healthy',     'Healthy'),
    ('degraded',    'Degraded'),
    ('unhealthy',   'Unhealthy'),
    ('unknown',     'Unknown'),
    ('maintenance', 'Maintenance'),
)
