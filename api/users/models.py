from django.contrib.auth.models import AbstractUser
from django.db import models
from core.models import TimeStampedModel
from core.validators import validate_phone_number
from django.utils.translation import gettext_lazy as _
import uuid
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import json
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator



class OTP(TimeStampedModel):
    OTP_TYPE_CHOICES = (
        ('registration', 'Registration'),
        ('login', 'Login'),
        ('password_reset', 'Password Reset'),
        ('phone_verify', 'Phone Verification'),
    )
    
    # user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otps')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPE_CHOICES, default='registration')
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    
    class Meta:
        app_label = 'users'
        verbose_name = _('OTP')
        verbose_name_plural = _('OTPs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code', 'is_used']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"OTP for {self.user.username} - {self.otp_type}"


class LoginHistory(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    is_successful = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'users'
        verbose_name = _('Login History')
        verbose_name_plural = _('Login Histories')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.created_at}"
    
    
class UserActivity(models.Model):
    """Track All User Activities"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'users'
        ordering = ['-timestamp']
        verbose_name = 'User Activity'
        verbose_name_plural = 'User Activities'
        indexes = [
            models.Index(fields=['-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"
    


class UserDevice(TimeStampedModel):
    # user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='devices')
    user = models.ForeignKey(
    settings.AUTH_USER_MODEL, 
    on_delete=models.CASCADE, 
    related_name='user_app_devices_list' # ইউনিক নাম দিন
)
    device_id = models.CharField(max_length=255, unique=True)
    device_name = models.CharField(max_length=100)
    device_type = models.CharField(max_length=50)  # android, ios, web
    fcm_token = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'users'
        verbose_name = _('User Device')
        verbose_name_plural = _('User Devices')

    def __str__(self):
        return f"{self.user.username} - {self.device_name}"
    
    
    
    # api/users/models.py (Add these models to your existing models.py)




# ==========================================
# 1. Device Fingerprint Model
# ==========================================
class DeviceFingerprint(models.Model):
    """
    Advanced device tracking using multiple fingerprinting techniques
    """
    fingerprint_hash = models.CharField(max_length=64, unique=True, db_index=True)
    
    # Browser fingerprints
    user_agent = models.TextField()
    canvas_fingerprint = models.CharField(max_length=64, null=True, blank=True)
    webgl_fingerprint = models.CharField(max_length=64, null=True, blank=True)
    audio_fingerprint = models.CharField(max_length=64, null=True, blank=True)
    
    # System info
    screen_resolution = models.CharField(max_length=20, null=True)
    timezone_offset = models.IntegerField(null=True)
    language = models.CharField(max_length=10, null=True)
    platform = models.CharField(max_length=50, null=True)
    
    # Advanced detection
    plugins = models.JSONField(default=list, blank=True)
    fonts = models.JSONField(default=list, blank=True)
    hardware_concurrency = models.IntegerField(null=True)
    device_memory = models.IntegerField(null=True)
    
    # Metadata
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    total_accounts = models.IntegerField(default=0)
    is_suspicious = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'users'
        db_table = 'device_fingerprints'
        indexes = [
            models.Index(fields=['fingerprint_hash']),
            models.Index(fields=['is_suspicious']),
            models.Index(fields=['is_blocked']),
        ]
    
    def __str__(self):
        return f"Device: {self.fingerprint_hash[:16]}..."
    
    def increment_account_count(self):
        """Increment total accounts created from this device"""
        self.total_accounts += 1
        if self.total_accounts >= 5:  # Suspicious if 5+ accounts
            self.is_suspicious = True
        if self.total_accounts >= 10:  # Auto-block at 10+ accounts
            self.is_blocked = True
        self.save()


# ==========================================
# 2. IP Reputation Model
# ==========================================
class IPReputation(models.Model):
    """
    IP address reputation and tracking system
    """
    REPUTATION_CHOICES = [
        ('trusted', 'Trusted'),
        ('neutral', 'Neutral'),
        ('suspicious', 'Suspicious'),
        ('blocked', 'Blocked'),
    ]
    
    ip_address = models.GenericIPAddressField(unique=True, db_index=True)
    reputation = models.CharField(max_length=20, choices=REPUTATION_CHOICES, default='neutral')
    
    # VPN/Proxy detection
    is_vpn = models.BooleanField(default=False)
    is_proxy = models.BooleanField(default=False)
    is_tor = models.BooleanField(default=False)
    is_datacenter = models.BooleanField(default=False)
    
    # Geographic info
    country_code = models.CharField(max_length=2, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    isp = models.CharField(max_length=200, null=True, blank=True)
    
    # Activity tracking
    total_registrations = models.IntegerField(default=0)
    total_logins = models.IntegerField(default=0)
    failed_login_attempts = models.IntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    
    # Fraud indicators
    fraud_score = models.IntegerField(default=0)  # 0-100
    is_blacklisted = models.BooleanField(default=False)
    blacklist_reason = models.TextField(null=True, blank=True)
    
    # Metadata
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'users'
        db_table = 'ip_reputations'
        verbose_name_plural = 'IP Reputations'
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['reputation']),
            models.Index(fields=['is_blacklisted']),
        ]
    
    def __str__(self):
        return f"{self.ip_address} - {self.reputation}"
    
    def increment_registration(self):
        """Track new registration from this IP"""
        self.total_registrations += 1
        if self.total_registrations >= 5:
            self.reputation = 'suspicious'
        if self.total_registrations >= 10:
            self.reputation = 'blocked'
            self.is_blacklisted = True
        self.save()
    
    def record_failed_login(self):
        """Record failed login attempt"""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        
        # Auto-block after 10 failed attempts in 1 hour
        if self.failed_login_attempts >= 10:
            one_hour_ago = timezone.now() - timedelta(hours=1)
            if self.last_failed_login and self.last_failed_login > one_hour_ago:
                self.is_blacklisted = True
                self.blacklist_reason = "Too many failed login attempts"
        self.save()


# ==========================================
# 3. User Account Link Model
# ==========================================
class UserAccountLink(models.Model):
    """
    Links users to devices and IPs for multi-account detection
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='account_links')
    device = models.ForeignKey(DeviceFingerprint, on_delete=models.CASCADE, related_name='users')
    ip_reputation = models.ForeignKey(IPReputation, on_delete=models.CASCADE, related_name='users')
    linked_account = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


    
    # Registration details
    registration_ip = models.GenericIPAddressField(blank=True, null=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    
    # Risk assessment
    risk_score = models.IntegerField(default=0)  # 0-100
    is_flagged = models.BooleanField(default=False)
    flag_reason = models.TextField(null=True, blank=True)
    
    class Meta:
        app_label = 'users'
        db_table = 'user_account_links'
        unique_together = [['user', 'device']]
        indexes = [
            models.Index(fields=['registration_ip']),
            models.Index(fields=['registration_date']),
            models.Index(fields=['is_flagged']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.device.fingerprint_hash[:16]}"


# ==========================================
# 4. User Behavior Model
# ==========================================
class UserBehavior(models.Model):
    """
    Track user behavior patterns for anomaly detection
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='behavior')
    action_type = models.CharField(max_length=100)


    
    # Login patterns
    avg_login_time = models.TimeField(null=True, blank=True)
    common_login_hours = models.JSONField(default=list, blank=True)  # [9, 10, 11, 14, 15]
    total_logins = models.IntegerField(default=0)
    
    # Activity patterns
    avg_session_duration = models.DurationField(null=True, blank=True)
    typical_actions = models.JSONField(default=list, blank=True)  # Common user actions
    
    # Device/IP patterns
    known_devices = models.ManyToManyField(DeviceFingerprint, blank=True)
    known_ips = models.ManyToManyField(IPReputation, blank=True)
    
    # Anomaly detection
    anomaly_score = models.IntegerField(default=0)  # 0-100
    last_anomaly_detected = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'users'
        db_table = 'user_behaviors'
        verbose_name_plural = 'User Behaviors'
    
    def __str__(self):
        return f"Behavior: {self.user.username}"


# ==========================================
# 5. Fraud Detection Log
# ==========================================
class FraudDetectionLog(models.Model):
    """
    Comprehensive fraud detection logging
    """
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    EVENT_TYPES = [
        ('vpn_detected', 'VPN Detected'),
        ('proxy_detected', 'Proxy Detected'),
        ('multi_account', 'Multi-Account Detected'),
        ('suspicious_ip', 'Suspicious IP'),
        ('rate_limit_exceeded', 'Rate Limit Exceeded'),
        ('device_banned', 'Device Banned'),
        ('ip_banned', 'IP Banned'),
        ('anomaly_detected', 'Behavioral Anomaly'),
        ('high_risk_score', 'High Risk Score'),
    ]
    
    # Event details
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    
    # Related objects
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    device = models.ForeignKey(DeviceFingerprint, on_delete=models.SET_NULL, null=True, blank=True)
    ip_reputation = models.ForeignKey(IPReputation, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Event data
    ip_address = models.GenericIPAddressField()
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    
    # Action taken
    action_taken = models.CharField(max_length=100, null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_frauds')
    
    # Timestamp
    detected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'users'
        db_table = 'fraud_detection_logs'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['event_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['detected_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.severity} - {self.detected_at}"


# ==========================================
# 6. Risk Score History
# ==========================================
class RiskScoreHistory(models.Model):
    """
    Track risk score changes over time
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='risk_history')
    
    # Score details
    risk_score = models.IntegerField()  # 0-100
    previous_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)



    
    # Factors contributing to score
    factors = models.JSONField(default=dict, blank=True)
    # Example: {
    #   "vpn_usage": 20,
    #   "multi_account": 30,RateLimitTracker
    #   "suspicious_ip": 15,
    #   "rapid_registration": 10
    # }
    
    # Metadata
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'users'
        db_table = 'risk_score_history'
        verbose_name_plural = 'Risk Score Histories'
        ordering = ['-calculated_at']
        indexes = [
            models.Index(fields=['user', 'calculated_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - Score: {self.risk_score}"


# ==========================================
# 7. Rate Limit Tracker
# ==========================================
class RateLimitTracker(models.Model):
    """
    Track rate limiting for IPs and devices
    """
    LIMIT_TYPE_CHOICES = [
        ('registration', 'Registration'),
        ('login', 'Login'),
        ('api', 'API Call'),
    ]
    
    # Identifier
    identifier = models.CharField(max_length=64, db_index=True)  # IP or device hash
    limit_type = models.CharField(max_length=20, choices=LIMIT_TYPE_CHOICES)
    
    # Rate tracking
    request_count = models.IntegerField(default=0)
    window_start = models.DateTimeField(auto_now_add=True)
    last_request = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(
    settings.AUTH_USER_MODEL, 
    on_delete=models.CASCADE, 
    null=True, 
    blank=True
    )
    endpoint = models.CharField(max_length=255)              
    count = models.IntegerField(default=0)                     
    created_at = models.DateTimeField(auto_now_add=True) 

    # Blocking
    is_blocked = models.BooleanField(default=False)
    block_until = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'users'
        db_table = 'rate_limit_trackers'
        unique_together = [['identifier', 'limit_type']]
        indexes = [
            models.Index(fields=['identifier', 'limit_type']),
            models.Index(fields=['is_blocked']),
        ]
    
    def __str__(self):
        return f"{self.identifier[:16]} - {self.limit_type}"
    
    def increment_request(self):
        """Increment request count and check if limit exceeded"""
        self.request_count += 1
        self.last_request = timezone.now()
        
        # Reset counter if window expired (1 hour window)
        if timezone.now() - self.window_start > timedelta(hours=1):
            self.request_count = 1
            self.window_start = timezone.now()
        
        # Block if exceeded (e.g., 5 registrations per hour)
        if self.limit_type == 'registration' and self.request_count > 5:
            self.is_blocked = True
            self.block_until = timezone.now() + timedelta(hours=24)
        
        self.save()
        return self.is_blocked
    
    
    
    # ==========================================
# 8. KYC Verification Model
# ==========================================
class KYCVerification(models.Model):
    """
    KYC (Know Your Customer) verification system
    """
    VERIFICATION_STATUS = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    DOCUMENT_TYPES = [
        ('nid', 'National ID Card'),
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
        ('voter_id', 'Voter ID'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_verification')
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='pending')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document_number = models.CharField(max_length=50)
    
    # Document images
    front_image = models.ImageField(upload_to='kyc/front/')
    back_image = models.ImageField(upload_to='kyc/back/', null=True, blank=True)
    selfie_image = models.ImageField(upload_to='kyc/selfie/')
    
    # Verification details
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_kyc')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'users'
        db_table = 'kyc_verifications'
        verbose_name = 'KYC Verification'
        verbose_name_plural = 'KYC Verifications'
    
    def __str__(self):
        return f"KYC: {self.user.username} - {self.verification_status}"


# ==========================================
# 9. User Level & Experience System
# ==========================================
class UserLevel(models.Model):
    """
    User level and experience points system
    """
    LEVEL_TYPES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
        ('diamond', 'Diamond'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='level_info')
    current_level = models.IntegerField(default=1)
    level_type = models.CharField(max_length=20, choices=LEVEL_TYPES, default='bronze')
    experience_points = models.IntegerField(default=0)
    
    # Level requirements
    xp_to_next_level = models.IntegerField(default=100)
    total_xp_earned = models.IntegerField(default=0)
    
    # Benefits
    task_reward_bonus = models.FloatField(default=1.0)  # Multiplier
    daily_task_limit_bonus = models.IntegerField(default=0)
    withdrawal_fee_discount = models.FloatField(default=0.0)  # Percentage
    priority_support = models.BooleanField(default=False)
    
    # Achievements
    badges = models.JSONField(default=list, blank=True)
    achievements_unlocked = models.JSONField(default=list, blank=True)
    
    # Statistics
    days_active = models.IntegerField(default=0)
    tasks_completed = models.IntegerField(default=0)
    referral_count = models.IntegerField(default=0)
    
    class Meta:
        app_label = 'users'
        db_table = 'user_levels'
        verbose_name = 'User Level'
        verbose_name_plural = 'User Levels'
    
    def __str__(self):
        return f"Level {self.current_level} {self.level_type}: {self.user.username}"


# # ==========================================
# # 10. User Notification Settings
# # ==========================================
class NotificationSettings(models.Model):
    """
    User notification preferences
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_settings')
    
    # Email notifications
    email_task_approved = models.BooleanField(default=True)
    email_task_rejected = models.BooleanField(default=True)
    email_withdrawal_processed = models.BooleanField(default=True)
    email_promotional = models.BooleanField(default=True)
    email_security_alerts = models.BooleanField(default=True)
    
    # Push notifications
    push_task_assigned = models.BooleanField(default=True)
    push_task_completed = models.BooleanField(default=True)
    push_reward_received = models.BooleanField(default=True)
    push_referral_joined = models.BooleanField(default=True)
    push_level_up = models.BooleanField(default=True)
    
    # SMS notifications
    sms_withdrawal_otp = models.BooleanField(default=True)
    sms_important_alerts = models.BooleanField(default=True)
    sms_promo_codes = models.BooleanField(default=False)
    
    # Frequency settings
    notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('hourly', 'Hourly Digest'),
            ('daily', 'Daily Digest'),
        ],
        default='immediate'
    )
    
    # Quiet hours
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'users'
        db_table = 'notification_settings'
        verbose_name = 'Notification Settings'
        verbose_name_plural = 'Notification Settings'
    
    def __str__(self):
        return f"Notification Settings: {self.user.username}"


# ==========================================
# 11. User Security Settings
# ==========================================
class SecuritySettings(models.Model):
    """
    User security preferences and 2FA settings
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='security_settings')
    
    # Two-Factor Authentication
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_method = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email'),
            ('sms', 'SMS'),
            ('authenticator', 'Authenticator App'),
        ],
        default='email'
    )
    authenticator_secret = models.CharField(max_length=32, blank=True, null=True)
    backup_codes = models.JSONField(default=list, blank=True)
    
    # Login security
    require_login_verification = models.BooleanField(default=False)
    login_verification_method = models.CharField(
        max_length=20,
        choices=[
            ('otp', 'OTP'),
            ('biometric', 'Biometric'),
            ('pattern', 'Pattern'),
        ],
        default='otp'
    )
    
    # Session security
    max_simultaneous_sessions = models.IntegerField(default=3)
    auto_logout_after = models.IntegerField(default=30)  # minutes
    remember_device_duration = models.IntegerField(default=30)  # days
    
    # Privacy settings
    show_online_status = models.BooleanField(default=True)
    show_last_seen = models.BooleanField(default=True)
    show_earnings = models.BooleanField(default=False)
    show_level = models.BooleanField(default=True)
    
    # Security alerts
    alert_on_new_device = models.BooleanField(default=True)
    alert_on_new_location = models.BooleanField(default=True)
    alert_on_failed_login = models.BooleanField(default=True)
    alert_on_withdrawal = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'users'
        db_table = 'security_settings'
        verbose_name = 'Security Settings'
        verbose_name_plural = 'Security Settings'
    
    def __str__(self):
        return f"Security Settings: {self.user.username}"


# ==========================================
# 12. User Statistics & Analytics
# ==========================================
class UserStatistics(models.Model):
    """
    Comprehensive user statistics and analytics
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='statistics')
    
    # Task statistics
    total_tasks_completed = models.IntegerField(default=0)
    tasks_completed_today = models.IntegerField(default=0)
    tasks_completed_this_week = models.IntegerField(default=0)
    tasks_completed_this_month = models.IntegerField(default=0)
    
    # Earning statistics
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    earned_today = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    earned_this_week = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    earned_this_month = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Referral statistics
    total_referrals = models.IntegerField(default=0)
    active_referrals = models.IntegerField(default=0)
    referral_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Withdrawal statistics
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    withdrawals_count = models.IntegerField(default=0)
    
    # Activity statistics
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    
    # Performance metrics
    task_approval_rate = models.FloatField(default=0)  # Percentage
    average_task_time = models.IntegerField(default=0)  # Seconds
    task_completion_rate = models.FloatField(default=0)  # Percentage
    
    # Daily limits tracking
    daily_task_quota_used = models.IntegerField(default=0)
    daily_earning_limit_used = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Achievement statistics
    badges_count = models.IntegerField(default=0)
    achievements_count = models.IntegerField(default=0)
    
    # Metadata
    statistics_updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'users'
        db_table = 'user_statistics'
        verbose_name = 'User Statistics'
        verbose_name_plural = 'User Statistics'
        indexes = [
            models.Index(fields=['user', 'total_earned']),
            models.Index(fields=['user', 'current_streak']),
        ]
    
    def __str__(self):
        return f"Statistics: {self.user.username}"


# ==========================================
# 13. User Preferences
# ==========================================
class UserPreferences(models.Model):
    """
    User customization and preferences
    """
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto (System)'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('bn', 'বাংলা'),
        ('hi', 'हिंदी'),
        ('ur', 'اردو'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preferences')
    
    # UI/UX preferences
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='auto')
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')
    
    # Dashboard preferences
    show_quick_stats = models.BooleanField(default=True)
    show_recent_activity = models.BooleanField(default=True)
    show_earning_chart = models.BooleanField(default=True)
    show_task_suggestions = models.BooleanField(default=True)
    
    # Task preferences
    default_task_category = models.ForeignKey('tasks.MasterTask', on_delete=models.SET_NULL, null=True, blank=True)
    preferred_task_types = models.JSONField(default=list, blank=True)
    auto_claim_tasks = models.BooleanField(default=False)
    task_reminder_enabled = models.BooleanField(default=True)
    task_reminder_time = models.TimeField(default='09:00')
    
    # Social preferences
    show_in_leaderboard = models.BooleanField(default=True)
    allow_friend_requests = models.BooleanField(default=True)
    show_referral_code = models.BooleanField(default=True)
    
    # Privacy preferences
    profile_visibility = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Public'),
            ('friends', 'Friends Only'),
            ('private', 'Private'),
        ],
        default='public'
    )
    
    # Accessibility
    font_size = models.CharField(max_length=10, default='medium')
    reduce_animations = models.BooleanField(default=False)
    high_contrast_mode = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'users'
        db_table = 'user_preferences'
        verbose_name = 'User Preferences'
        verbose_name_plural = 'User Preferences'
    
    def __str__(self):
        return f"Preferences: {self.user.username}"
    


class User(AbstractUser):
    """কাস্টম ইউজার মডেল - যেখানে সব ফিল্ড একসাথে করা হয়েছে"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    ROLE_CHOICES = (
        ('user', 'User'),
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
    )
    
    USER_TIER_CHOICES = [
        ('FREE', 'Free'),
        ('BRONZE', 'Bronze'),
        ('SILVER', 'Silver'),
        ('GOLD', 'Gold'),
        ('PLATINUM', 'Platinum'),
    ]

    # uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # uid ফিল্ডটিকে primary_key করবেন না, এটি একটি আলাদা ইউনিক আইডেন্টিফায়ার হিসেবে থাকবে
    uid = models.UUIDField(
    default=uuid.uuid4, 
    editable=False, 
    unique=True,
    null=True # সাময়িকভাবে null=True দিন যাতে পুরনো ডাটা মাইগ্রেট হতে সমস্যা না করে
    )
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    # phone_number = models.CharField(max_length=20, blank=True, null=True) 
    
    # ব্যালেন্স সংক্রান্ত
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # রেফারেল সংক্রান্ত
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    referred_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals_list'
    )
    
    tier = models.CharField(max_length=10, choices=USER_TIER_CHOICES, default='FREE')
    country = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    # টাইমস্ট্যাম্প
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        app_label = 'users'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} - ${self.balance}"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = f"EARN{str(uuid.uuid4())[:8].upper()}"
        super().save(*args, **kwargs)




class UserProfile(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    
    # Personal Information
    profile_id = models.CharField(max_length=20, unique=True, blank=True, null=True, editable=False)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    bio = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, default='Bangladesh')
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    nid_number = models.CharField(max_length=20, blank=True, null=True, unique=True)
    
    # Points and Earnings
    total_points = models.PositiveIntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Verification Status
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    identity_verified = models.BooleanField(default=False)
    
    # Account Status
    ACCOUNT_STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('banned', 'Banned'),
    )
    account_status = models.CharField(
        max_length=20, 
        choices=ACCOUNT_STATUS_CHOICES, 
        default='active'
    )
    
    # Additional Fields
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=10, blank=True, null=True)
    
    # Referral System
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    referred_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name='referrals')
    
    # Account Features
    is_premium = models.BooleanField(default=False)
    is_affiliate = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'users'
    
    
class UserRank(models.Model):
    """User Rank/Badge System"""
    
    RANK_CHOICES = [
        ('Bronze', 'Bronze'),
        ('Silver', 'Silver'),
        ('Gold', 'Gold'),
        ('Platinum', 'Platinum'),
        ('Diamond', 'Diamond'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rank')
    rank = models.CharField(max_length=20, choices=RANK_CHOICES, default='Bronze')
    points = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    badge_icon = models.CharField(max_length=50, blank=True, null=True)
    next_rank_points = models.IntegerField(default=100)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'users'
        verbose_name = 'User Rank'
        verbose_name_plural = 'User Ranks'
    
    def __str__(self):
        return f"{self.user.username} - {self.rank} ({self.points} points)"
    
    def update_rank(self):
        """Auto Update Rank based on Points"""
        if self.points >= 10000:
            self.rank = 'Diamond'
            self.next_rank_points = 0
        elif self.points >= 5000:
            self.rank = 'Platinum'
            self.next_rank_points = 10000
        elif self.points >= 2000:
            self.rank = 'Gold'
            self.next_rank_points = 5000
        elif self.points >= 500:
            self.rank = 'Silver'
            self.next_rank_points = 2000
        else:
            self.rank = 'Bronze'
            self.next_rank_points = 500
        self.save()