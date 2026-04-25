from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import random
import string
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.conf import settings
import os
# Notice is defined below in this file
from api.tenants.models import Tenant


# ==================== CUSTOM USER MODEL ====================
class CustomUser(AbstractUser):
    # --- Multi-tenant ---
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(app_label)s_%(class)s_tenant')
    # --- Identification ---
    user_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    refer_code = models.CharField(max_length=10, unique=True, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    
    # --- Earning System ---
    coin_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    
    # --- Profile & Contact ---
    full_name = models.CharField(max_length=200, null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, unique=True, null=True)
    
    # --- Status & Verification ---
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)  # KYC
    
    # --- Demographics ---
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True, choices=[
        ('male', 'Male'), ('female', 'Female'), ('other', 'Other')
    ])
    country = models.CharField(max_length=100, default='Bangladesh', null=True, blank=True)
    language = models.CharField(max_length=10, default='bn', null=True, blank=True)
    timezone = models.CharField(max_length=50, default='Asia/Dhaka', null=True, blank=True)
    
    # --- Account Security & Level ---
    account_level = models.CharField(max_length=20, default='normal', choices=[
        ('normal', 'Normal'), ('vip', 'VIP'), ('blocked', 'Blocked')
    ])
    is_2fa_enabled = models.BooleanField(default=False)
    device_count = models.IntegerField(default=0)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # --- Authentication fields fix ---
    groups = models.ManyToManyField(
        Group,
        related_name='%(app_label)s_%(class)s_tenant',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='%(app_label)s_%(class)s_tenant',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    class Meta:
        db_table = 'users.User'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-date_joined']

    def save(self, *args, **kwargs):
        if not self.user_id:
            self.user_id = f"USER{random.randint(100000, 999999)}"
        if not self.refer_code:
            self.refer_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


# ==================== ১. FRAUD DETECTION SYSTEM ====================
class UserDevice(models.Model):
    """
    ইউজারের ডিভাইস ট্র্যাকিং ফ্রড ডিটেকশনের জন্য
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_userdevice_user',
        verbose_name=_("User")
    )
    
    device_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("Device ID"),
        help_text=_("Unique device identifier (UUID)")
    )
    
    device_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Device Name")
    )
    
    device_model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Device Model")
    )
    
    device_os = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Operating System")
    )
    
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('desktop', 'Desktop'),
            ('other', 'Other'),
        ],
        default='mobile',
        verbose_name=_("Device Type")
    )
    
    ip_address = models.GenericIPAddressField(
        verbose_name=_("IP Address")
    )
    
    is_vpn_detected = models.BooleanField(
        default=False,
        verbose_name=_("VPN Detected")
    )
    
    is_proxy_detected = models.BooleanField(
        default=False,
        verbose_name=_("Proxy Detected")
    )
    
    is_tor_detected = models.BooleanField(
        default=False,
        verbose_name=_("Tor Network Detected")
    )
    
    location_country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Country")
    )
    
    location_city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("City")
    )
    
    location_region = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Region")
    )
    
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Latitude")
    )
    
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Longitude")
    )
    
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("User Agent")
    )
    
    is_primary = models.BooleanField(
        default=False,
        verbose_name=_("Primary Device")
    )
    
    is_blocked = models.BooleanField(
        default=False,
        verbose_name=_("Blocked")
    )
    
    blocked_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Blocked Reason")
    )
    
    fraud_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Fraud Score"),
        help_text=_("0-100, higher means more suspicious")
    )
    
    last_used = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Last Used")
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    
    class Meta:
        db_table = 'user_devices'
        verbose_name = _('User Device')
        verbose_name_plural = _('User Devices')
        ordering = ['-last_used']
        unique_together = ['user', 'device_id']
        indexes = [
            models.Index(fields=['device_id'], name='idx_device_id_001'),
            models.Index(fields=['ip_address'], name='idx_ip_address_002'),
            models.Index(fields=['fraud_score'], name='idx_fraud_score_003'),
            models.Index(fields=['is_vpn_detected'], name='idx_is_vpn_detected_004'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.device_id[:10]}..."

    def clean(self):
        """Validate device data"""
        if self.fraud_score > 80 and not self.is_blocked:
            raise ValidationError(
                _("Device with fraud score > 80 should be blocked.")
            )

    @property
    def is_suspicious(self):
        """Check if device is suspicious"""
        return (
            self.is_vpn_detected or
            self.is_proxy_detected or
            self.is_tor_detected or
            self.fraud_score > 50
        )

    @property
    def location(self):
        """Get formatted location"""
        if self.location_city and self.location_country:
            return f"{self.location_city}, {self.location_country}"
        return self.location_country or _("Unknown")


class DeviceLoginHistory(models.Model):
    """
    Device login history for tracking
    """

    device = models.ForeignKey(
        UserDevice,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant',
        verbose_name=_("Device")
    )
    
    login_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Login Time")
    )
    
    logout_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Logout Time")
    )
    
    session_duration = models.IntegerField(
        default=0,
        verbose_name=_("Session Duration (seconds)")
    )
    
    ip_address = models.GenericIPAddressField(
        verbose_name=_("IP Address")
    )
    
    is_successful = models.BooleanField(
        default=True,
        verbose_name=_("Login Successful")
    )
    
    failure_reason = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Failure Reason")
    )
    
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("User Agent")
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata")
    )
    
    class Meta:
        db_table = 'device_login_history'
        verbose_name = _('Device Login History')
        verbose_name_plural = _('Device Login History')
        ordering = ['-login_time']
        indexes = [
            models.Index(fields=['device', 'login_time'], name='idx_device_login_time_005'),
            models.Index(fields=['is_successful'], name='idx_is_successful_006'),
        ]

    def __str__(self):
        return f"{self.device.user.username} - {self.login_time}"


# ==================== ২. TIERED REFERRAL SYSTEM ====================
class ReferralLevel(models.Model):
    """
    টায়ার্ড রেফারেল সিস্টেম - প্রতিটি লেভেলের জন্য আলাদা কমিশন
    """

    level_number = models.IntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Level Number"),
        help_text=_("1 for direct referrals, 2 for indirect, etc.")
    )
    
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Commission Percentage"),
        help_text=_("Percentage commission for this level")
    )
    
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Description")
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    
    min_referrals = models.IntegerField(
        default=0,
        verbose_name=_("Minimum Referrals"),
        help_text=_("Minimum referrals needed for this level")
    )
    
    bonus_coins = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Bonus Coins"),
        help_text=_("Extra bonus coins for reaching this level")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'referral_levels'
        verbose_name = _('Referral Level')
        verbose_name_plural = _('Referral Levels')
        ordering = ['level_number']
        indexes = [
            models.Index(fields=['level_number'], name='idx_level_number_007'),
            models.Index(fields=['is_active'], name='idx_is_active_008'),
        ]

    def __str__(self):
        return f"Level {self.level_number} - {self.commission_percentage}%"

    def clean(self):
        """Validate referral level"""
        if self.level_number < 1:
            raise ValidationError(_("Level number must be at least 1."))
        
        if self.commission_percentage > 100:
            raise ValidationError(_("Commission cannot exceed 100%."))


class UserReferralNetwork(models.Model):
    """
    ইউজারের সম্পূর্ণ রেফারেল নেটওয়ার্ক ট্র্যাকিং
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='api_userreferralnetwork_user',
        verbose_name=_("User")
    )
    
    direct_referrals = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='api_userreferralnetwork_direct_referrals',
        blank=True,
        verbose_name=_("Direct Referrals")
    )
    
    total_referrals = models.IntegerField(
        default=0,
        verbose_name=_("Total Referrals"),
        help_text=_("Direct + indirect referrals")
    )
    
    active_referrals = models.IntegerField(
        default=0,
        verbose_name=_("Active Referrals")
    )
    
    total_commission_earned = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Total Commission Earned")
    )
    
    level_1_commission = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Level 1 Commission")
    )
    
    level_2_commission = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Level 2 Commission")
    )
    
    level_3_commission = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Level 3 Commission")
    )
    
    current_level = models.ForeignKey(
        ReferralLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Current Level")
    )
    
    last_commission_calculation = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Commission Calculation")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_referral_networks'
        verbose_name = _('User Referral Network')
        verbose_name_plural = _('User Referral Networks')
        indexes = [
            models.Index(fields=['total_referrals'], name='idx_total_referrals_009'),
            models.Index(fields=['total_commission_earned'], name='idx_total_commission_earne_b69'),
        ]

    def __str__(self):
        return f"{self.user.username}'s Referral Network"

    @property
    def referral_link(self):
        """Generate referral link"""
        return f"{settings.SITE_URL}/register?ref={self.user.refer_code}"

    def calculate_total_referrals(self):
        """Calculate total referrals recursively"""
        total = self.direct_referrals.count()
        
        # Calculate indirect referrals (level 2, 3, etc.)
        for direct_ref in self.direct_referrals.all():
            try:
                direct_network = direct_ref.referral_network
                total += direct_network.direct_referrals.count()
                
                # Level 3 referrals
                for level2_ref in direct_network.direct_referrals.all():
                    try:
                        level2_network = level2_ref.referral_network
                        total += level2_network.direct_referrals.count()
                    except:
                        pass
            except:
                pass
        
        self.total_referrals = total
        self.save()
        return total


class ReferralCommission(models.Model):
    """
    রেফারেল কমিশনের হিসাব
    """

    TRANSACTION_TYPES = [
        ('signup', 'Signup Bonus'),
        ('earning', 'Earning Commission'),
        ('withdrawal', 'Withdrawal Commission'),
        ('bonus', 'Special Bonus'),
    ]
    
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_referralcommission_referrer',
        verbose_name=_("Referrer")
    )
    
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_referralcommission_referred_user',
        verbose_name=_("Referred User")
    )
    
    level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Referral Level"),
        help_text=_("1 for direct, 2 for indirect, etc.")
    )
    
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        verbose_name=_("Transaction Type")
    )
    
    base_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Base Amount")
    )
    
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_("Commission Percentage")
    )
    
    commission_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Commission Amount")
    )
    
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Description")
    )
    
    is_paid = models.BooleanField(
        default=False,
        verbose_name=_("Is Paid")
    )
    
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Paid At")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'referral_commissions'
        verbose_name = _('Referral Commission')
        verbose_name_plural = _('Referral Commissions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['referrer', 'level'], name='idx_referrer_level_011'),
            models.Index(fields=['is_paid'], name='idx_is_paid_012'),
            models.Index(fields=['created_at'], name='idx_created_at_013'),
        ]

    def __str__(self):
        return f"{self.referrer.username} → {self.referred_user.username} (L{self.level}): {self.commission_amount}"


# ==================== ৩. DAILY STREAK & REWARDS ====================
class UserStreak(models.Model):
    """
    ডেইলি স্ট্রিক সিস্টেম - ইউজাররা প্রতিদিন অ্যাপ ওপেন করার জন্য রিওয়ার্ড
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='api_userstreak_user',
        verbose_name=_("User")
    )
    
    current_streak = models.IntegerField(
        default=0,
        verbose_name=_("Current Streak"),
        help_text=_("Consecutive days of login")
    )
    
    longest_streak = models.IntegerField(
        default=0,
        verbose_name=_("Longest Streak")
    )
    
    last_login_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Last Login Date")
    )
    
    total_logins = models.IntegerField(
        default=0,
        verbose_name=_("Total Logins")
    )
    
    streak_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Streak Start Date")
    )
    
    today_logged_in = models.BooleanField(
        default=False,
        verbose_name=_("Today Logged In")
    )
    
    # Milestones
    milestone_7_days = models.BooleanField(
        default=False,
        verbose_name=_("7 Days Milestone")
    )
    
    milestone_30_days = models.BooleanField(
        default=False,
        verbose_name=_("30 Days Milestone")
    )
    
    milestone_90_days = models.BooleanField(
        default=False,
        verbose_name=_("90 Days Milestone")
    )
    
    milestone_180_days = models.BooleanField(
        default=False,
        verbose_name=_("180 Days Milestone")
    )
    
    milestone_365_days = models.BooleanField(
        default=False,
        verbose_name=_("365 Days Milestone")
    )
    
    # Rewards earned
    total_streak_rewards = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Total Streak Rewards")
    )
    
    last_reward_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Last Reward Date")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_streaks'
        verbose_name = _('User Streak')
        verbose_name_plural = _('User Streaks')
        indexes = [
            models.Index(fields=['current_streak'], name='idx_current_streak_014'),
            models.Index(fields=['last_login_date'], name='idx_last_login_date_015'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.current_streak} days streak"

    def update_streak(self):
        """Update user streak"""
        today = timezone.now().date()
        
        if not self.last_login_date:
            # First login
            self.current_streak = 1
            self.streak_start_date = today
            self.today_logged_in = True
            self.total_logins = 1
        elif self.last_login_date == today:
            # Already logged in today
            if not self.today_logged_in:
                self.today_logged_in = True
                self.total_logins += 1
        else:
            # Check if consecutive day
            days_diff = (today - self.last_login_date).days
            
            if days_diff == 1:
                # Consecutive day
                self.current_streak += 1
            elif days_diff > 1:
                # Streak broken
                if self.current_streak > self.longest_streak:
                    self.longest_streak = self.current_streak
                self.current_streak = 1
                self.streak_start_date = today
            
            self.today_logged_in = True
            self.total_logins += 1
        
        self.last_login_date = today
        self.check_milestones()
        self.save()

    def check_milestones(self):
        """Check and update milestones"""
        milestones = [
            (7, 'milestone_7_days'),
            (30, 'milestone_30_days'),
            (90, 'milestone_90_days'),
            (180, 'milestone_180_days'),
            (365, 'milestone_365_days'),
        ]
        
        for days, field_name in milestones:
            if self.current_streak >= days and not getattr(self, field_name):
                setattr(self, field_name, True)
                # Award milestone bonus
                self.award_milestone_reward(days)

    def award_milestone_reward(self, days):
        """Award milestone reward"""
        # Calculate reward based on days
        reward_map = {
            7: 100,
            30: 500,
            90: 1500,
            180: 3000,
            365: 10000,
        }
        
        reward = reward_map.get(days, 0)
        if reward > 0:
            self.total_streak_rewards += Decimal(reward)
            self.last_reward_date = timezone.now().date()
            
            # Create streak reward record
            StreakReward.objects.create(
                user=self.user,
                streak_days=days,
                reward_amount=reward,
                milestone=True
            )
            
            # Update user balance
            self.user.coin_balance += Decimal(reward)
            self.user.total_earned += Decimal(reward)
            self.user.save()

    @property
    def next_milestone(self):
        """Get next milestone"""
        milestones = [7, 30, 90, 180, 365]
        for milestone in milestones:
            if self.current_streak < milestone and not getattr(self, f'milestone_{milestone}_days'):
                return {
                    'days': milestone,
                    'remaining': milestone - self.current_streak,
                    'progress': (self.current_streak / milestone) * 100
                }
        return None

    @property
    def is_streak_active(self):
        """Check if streak is still active (logged in today)"""
        return self.today_logged_in and self.last_login_date == timezone.now().date()


class StreakReward(models.Model):
    """
    স্ট্রিক রিওয়ার্ড হিস্ট্রি
    """

    REWARD_TYPES = [
        ('daily', 'Daily Login'),
        ('milestone', 'Milestone'),
        ('bonus', 'Bonus'),
        ('special', 'Special Event'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_streakreward_user',
        verbose_name=_("User")
    )
    
    reward_type = models.CharField(
        max_length=20,
        choices=REWARD_TYPES,
        verbose_name=_("Reward Type")
    )
    
    streak_days = models.IntegerField(
        default=0,
        verbose_name=_("Streak Days")
    )
    
    reward_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Reward Amount")
    )
    
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Description")
    )
    
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'streak_rewards'
        verbose_name = _('Streak Reward')
        verbose_name_plural = _('Streak Rewards')
        ordering = ['-awarded_at']
        indexes = [
            models.Index(fields=['user', 'awarded_at'], name='idx_user_awarded_at_016'),
            models.Index(fields=['reward_type'], name='idx_reward_type_017'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.reward_amount} coins ({self.reward_type})"


# ==================== ৪. DYNAMIC OFFERWALL TRACKING ====================
class OfferwallNetwork(models.Model):
    """
    অফারওয়াল নেটওয়ার্ক ডিটেইলস
    """

    NETWORK_CHOICES = [
        ('adgem', 'AdGem'),
        ('adgate', 'AdGate'),
        ('offertoro', 'OfferToro'),
        ('personaly', 'Persona.ly'),
        ('tapjoy', 'Tapjoy'),
        ('ironsource', 'IronSource'),
        ('fyber', 'Fyber'),
        ('vungle', 'Vungle'),
        ('unity', 'Unity Ads'),
        ('applovin', 'AppLovin'),
        ('admob', 'AdMob'),
        ('custom', 'Custom'),
    ]
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Network Name")
    )
    
    network_code = models.CharField(
        max_length=50,
        unique=True,
        choices=NETWORK_CHOICES,
        verbose_name=_("Network Code")
    )
    
    api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("API Key")
    )
    
    secret_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Secret Key")
    )
    
    postback_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Postback URL")
    )
    
    base_url = models.URLField(
        verbose_name=_("Base URL")
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Commission Rate"),
        help_text=_("Our commission from this network (%)")
    )
    
    min_payout = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Minimum Payout")
    )
    
    avg_epc = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Average EPC")
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description")
    )
    
    logo = models.ImageField(
        upload_to='offerwall_logos/',
        blank=True,
        null=True,
        verbose_name=_("Logo")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offerwall_networks'
        verbose_name = _('Offerwall Network')
        verbose_name_plural = _('Offerwall Networks')
        ordering = ['name']
        indexes = [
            models.Index(fields=['network_code'], name='idx_network_code_018'),
            models.Index(fields=['is_active'], name='idx_is_active_019'),
        ]

    def __str__(self):
        return self.name


class OfferwallOffer(models.Model):
    """
    অফারওয়াল অফার ডিটেইলস
    """

    OFFER_TYPES = [
        ('install', 'App Install'),
        ('survey', 'Survey'),
        ('quiz', 'Quiz'),
        ('video', 'Video Ad'),
        ('offer', 'Offer'),
        ('trial', 'Free Trial'),
        ('subscription', 'Subscription'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('expired', 'Expired'),
        ('pending', 'Pending Approval'),
    ]
    
    offer_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Offer ID")
    )
    
    network = models.ForeignKey(
        OfferwallNetwork,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant',
        verbose_name=_("Network")
    )
    
    title = models.CharField(
        max_length=255,
        verbose_name=_("Offer Title")
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description")
    )
    
    offer_type = models.CharField(
        max_length=20,
        choices=OFFER_TYPES,
        verbose_name=_("Offer Type")
    )
    
    requirements = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Requirements")
    )
    
    instructions = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Instructions")
    )
    
    # Payout Information
    payout_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Payout Amount")
    )
    
    currency = models.CharField(
        max_length=10,
        default='USD',
        verbose_name=_("Currency")
    )
    
    user_reward = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("User Reward (Coins)")
    )
    
    # Targeting
    target_countries = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Target Countries"),
        help_text=_("List of country codes")
    )
    
    target_devices = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Target Devices"),
        help_text=_("List of device types")
    )
    
    min_age = models.IntegerField(
        default=13,
        verbose_name=_("Minimum Age")
    )
    
    max_age = models.IntegerField(
        default=100,
        verbose_name=_("Maximum Age")
    )
    
    # Stats
    total_completions = models.IntegerField(
        default=0,
        verbose_name=_("Total Completions")
    )
    
    total_conversions = models.IntegerField(
        default=0,
        verbose_name=_("Total Conversions")
    )
    
    conversion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Conversion Rate (%)")
    )
    
    total_payout = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Total Payout")
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_("Status")
    )
    
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_("Is Featured")
    )
    
    is_hot = models.BooleanField(
        default=False,
        verbose_name=_("Is Hot Offer")
    )
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expiry_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Expiry Date")
    )
    
    # Additional
    thumbnail_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Thumbnail URL")
    )
    
    preview_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Preview URL")
    )
    
    tracking_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Tracking URL")
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata")
    )

    class Meta:
        db_table = 'offerwall_offers'
        verbose_name = _('Offerwall Offer')
        verbose_name_plural = _('Offerwall Offers')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['offer_id'], name='idx_offer_id_020'),
            models.Index(fields=['network', 'status'], name='idx_network_status_021'),
            models.Index(fields=['offer_type'], name='idx_offer_type_022'),
            models.Index(fields=['is_featured'], name='idx_is_featured_023'),
            models.Index(fields=['expiry_date'], name='idx_expiry_date_024'),
        ]

    def __str__(self):
        return f"{self.title} ({self.network.name})"

    @property
    def is_available(self):
        """Check if offer is available"""
        if self.status != 'active':
            return False
        
        if self.expiry_date and timezone.now() > self.expiry_date:
            return False
        
        return True

    @property
    def display_reward(self):
        """Get display reward"""
        return f"{self.user_reward} coins"

    def increment_completions(self):
        """Increment completion count"""
        self.total_completions += 1
        self.save()


class OfferwallLog(models.Model):
    """
    ইউজারের অফার কমপ্লিশন লগ - তুমি যে মডেল চেয়েছো
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('fraud', 'Fraud Detected'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_offerwalllog_user',
        verbose_name=_("User")
    )
    
    offer = models.ForeignKey(
        OfferwallOffer,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant',
        verbose_name=_("Offer")
    )
    
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Transaction ID")
    )
    
    network_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Network Transaction ID")
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Status")
    )
    
    reward_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Reward Amount")
    )
    
    payout_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Payout Amount")
    )
    
    ip_address = models.GenericIPAddressField(
        verbose_name=_("IP Address")
    )
    
    device_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Device ID")
    )
    
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("User Agent")
    )
    
    clicked_at = models.DateTimeField(
        verbose_name=_("Clicked At")
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Completed At")
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Approved At")
    )
    
    credited_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Credited At")
    )
    
    fraud_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Fraud Score")
    )
    
    fraud_check_result = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Fraud Check Result")
    )
    
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Rejection Reason")
    )
    
    network_response = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Network Response")
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offerwall_logs'
        verbose_name = _('Offerwall Log')
        verbose_name_plural = _('Offerwall Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id'], name='idx_transaction_id_025'),
            models.Index(fields=['user', 'status'], name='idx_user_status_026'),
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_027'),
            models.Index(fields=['offer', 'status'], name='idx_offer_status_028'),
            models.Index(fields=['fraud_score'], name='idx_fraud_score_029'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.offer.title} - {self.status}"

    def mark_as_completed(self):
        """Mark as completed"""
        if self.status == 'pending':
            self.status = 'approved'
            self.completed_at = timezone.now()
            self.save()
            
            # Award coins to user
            self.user.coin_balance += self.reward_amount
            self.user.total_earned += self.reward_amount
            self.user.save()
            
            # Update offer stats
            self.offer.total_completions += 1
            self.offer.total_conversions += 1
            self.offer.total_payout += self.reward_amount
            self.offer.save()

    @property
    def processing_time(self):
        """Get processing time in seconds"""
        if self.completed_at and self.clicked_at:
            return (self.completed_at - self.clicked_at).total_seconds()
        return None

    @property
    def is_fraudulent(self):
        """Check if log is fraudulent"""
        return self.fraud_score > 70 or self.status == 'fraud'


# # ==================== ৫. NOTIFICATION HISTORY ====================
# class Notification(models.Model):

#     """
#     নোটিফিকেশন হিস্ট্রি - তুমি যে মডেল চেয়েছো
#     """
#     NOTIFICATION_TYPES = [
#         ('system', 'System Notification'),
#         ('payment', 'Payment Notification'),
#         ('offer', 'Offer Notification'),
#         ('referral', 'Referral Notification'),
#         ('announcement', 'Announcement'),
#         ('alert', 'Alert'),
#         ('promotion', 'Promotion'),
#         ('update', 'Update'),
#     ]
    
#     PRIORITY_CHOICES = [
#         ('low', 'Low'),
#         ('normal', 'Normal'),
#         ('high', 'High'),
#         ('urgent', 'Urgent'),
#     ]
    
#     CHANNEL_CHOICES = [
#         ('in_app', 'In-App'),
#         ('email', 'Email'),
#         ('sms', 'SMS'),
#         ('push', 'Push Notification'),
#         ('all', 'All Channels'),
#     ]
    
#     # Recipient
#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name='api_offerwalllog_tenant',
#         verbose_name=_("User")
#     )
    
#     # Notification details
#     title = models.CharField(
#         max_length=255,
#         verbose_name=_("Title")
#     )
    
#     message = models.TextField(
#         verbose_name=_("Message")
#     )
    
#     notification_type = models.CharField(
#         max_length=20,
#         choices=NOTIFICATION_TYPES,
#         default='system',
#         verbose_name=_("Notification Type")
#     )
    
#     priority = models.CharField(
#         max_length=10,
#         choices=PRIORITY_CHOICES,
#         default='normal',
#         verbose_name=_("Priority")
#     )
    
#     channels = models.JSONField(
#         default=list,
#         verbose_name=_("Channels"),
#         help_text=_("List of delivery channels")
#     )
    
#     # Status
#     is_read = models.BooleanField(
#         default=False,
#         verbose_name=_("Is Read")
#     )
    
#     is_sent = models.BooleanField(
#         default=False,
#         verbose_name=_("Is Sent")
#     )
    
#     read_at = models.DateTimeField(
#         null=True,
#         blank=True,
#         verbose_name=_("Read At")
#     )
    
#     sent_at = models.DateTimeField(
#         null=True,
#         blank=True,
#         verbose_name=_("Sent At")
#     )
    
#     # Actions
#     action_url = models.URLField(
#         blank=True,
#         null=True,
#         verbose_name=_("Action URL")
#     )
    
#     action_text = models.CharField(
#         max_length=100,
#         blank=True,
#         null=True,
#         verbose_name=_("Action Text")
#     )
    
#     # Categorization
#     category = models.CharField(
#         max_length=50,
#         blank=True,
#         null=True,
#         verbose_name=_("Category")
#     )
    
#     tags = models.JSONField(
#         default=list,
#         blank=True,
#         verbose_name=_("Tags")
#     )
    
#     # Sender
#     sender = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='api_offerwalllog_tenant',
#         verbose_name=_("Sender")
#     )
    
#     # Analytics
#     opened_count = models.IntegerField(
#         default=0,
#         verbose_name=_("Opened Count")
#     )
    
#     clicked_count = models.IntegerField(
#         default=0,
#         verbose_name=_("Clicked Count")
#     )
    
#     # Metadata
#     metadata = models.JSONField(
#         default=dict,
#         blank=True,
#         verbose_name=_("Metadata")
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'notifications'
#         verbose_name = _('Notification')
#         verbose_name_plural = _('Notifications')
#         ordering = ['-created_at']
#         indexes = [
#             models.Index(fields=['user', 'is_read'], name='idx_user_is_read_030'),
#             models.Index(fields=['notification_type'], name='idx_notification_type_031'),
#             models.Index(fields=['is_sent'], name='idx_is_sent_032'),
#             models.Index(fields=['created_at'], name='idx_created_at_033'),
#         ]

#     def __str__(self):
#         return f"{self.title} - {self.user.username}"

#     def mark_as_read(self):
#         """Mark notification as read"""
#         if not self.is_read:
#             self.is_read = True
#             self.read_at = timezone.now()
#             self.save()

#     def mark_as_sent(self):
#         """Mark notification as sent"""
#         if not self.is_sent:
#             self.is_sent = True
#             self.sent_at = timezone.now()
#             self.save()

#     @property
#     def short_message(self):
#         """Get shortened message"""
#         if len(self.message) > 100:
#             return self.message[:100] + "..."
#         return self.message

#     @property
#     def delivery_status(self):
#         """Get delivery status"""
#         if not self.is_sent:
#             return 'pending'
#         elif self.is_sent and not self.is_read:
#             return 'sent'
#         elif self.is_read:
#             return 'read'
#         return 'unknown'


class NotificationTemplate(models.Model):
    """
    নোটিফিকেশন টেম্পলেট রিউজ করার জন্য
    """

    TEMPLATE_TYPES = [
        ('welcome', 'Welcome Message'),
        ('payment_approved', 'Payment Approved'),
        ('payment_rejected', 'Payment Rejected'),
        ('offer_completed', 'Offer Completed'),
        ('referral_earned', 'Referral Earned'),
        ('streak_milestone', 'Streak Milestone'),
        ('withdrawal_request', 'Withdrawal Request'),
        ('account_verified', 'Account Verified'),
        ('security_alert', 'Security Alert'),
        ('promotional', 'Promotional'),
        ('custom', 'Custom'),
    ]
    
    template_name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Template Name")
    )
    
    template_type = models.CharField(
        max_length=50,
        choices=TEMPLATE_TYPES,
        verbose_name=_("Template Type")
    )
    
    subject = models.CharField(
        max_length=255,
        verbose_name=_("Subject")
    )
    
    message = models.TextField(
        verbose_name=_("Message")
    )
    
    variables = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Variables"),
        help_text=_("Available variables in template")
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_templates'
        verbose_name = _('Notification Template')
        verbose_name_plural = _('Notification Templates')
        ordering = ['template_name']
        indexes = [
            models.Index(fields=['template_type'], name='idx_template_type_034'),
            models.Index(fields=['is_active'], name='idx_is_active_035'),
        ]

    def __str__(self):
        return self.template_name

    def format_message(self, context):
        """Format message with context"""
        message = self.message
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            message = message.replace(placeholder, str(value))
        return message


# ==================== EXISTING MODELS ====================
class Notice(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    message = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Notice')
        verbose_name_plural = _('Notices')

    def __str__(self):
        return self.message[:50] + "..."


class EarningTask(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    TASK_TYPES = [
        ('ad_watch', 'Watch Ads'),
        ('app_install', 'App Install'),
        ('survey', 'Survey'),
        ('quiz', 'Quiz'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, null=True, blank=True)
    coins_earned = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Earning Task')
        verbose_name_plural = _('Earning Tasks')

    def __str__(self):
        return f"{self.user.username} - {self.task_type}"


class PaymentRequest(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('approved', 'Approved'),
        ('paid', 'Paid'), ('rejected', 'Rejected'),
    ]
    
    PAYMENT_METHODS = [
        ('bkash', 'বিকাশ'), ('nagad', 'নগদ'), ('rocket', 'রকেট'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    coins_deducted = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, null=True, blank=True)
    account_number = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-requested_at']
        verbose_name = _('Payment Request')
        verbose_name_plural = _('Payment Requests')

    def __str__(self):
        return f"{self.user.username} - {self.amount}"


class PaymentHistory(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    username = models.CharField(max_length=100, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(max_length=20, null=True, blank=True)
    paid_at = models.DateTimeField(auto_now_add=True)
    is_real = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-paid_at']
        verbose_name = _('Payment History')
        verbose_name_plural = _('Payment Histories')

    def __str__(self):
        return f"{self.username} - {self.amount}"


# ==================== SIGNAL HANDLERS ====================

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """Create related profiles when user is created"""
    if created:
        # Create UserStreak
        UserStreak.objects.create(user=instance)
        
        # Create UserReferralNetwork
        UserReferralNetwork.objects.create(user=instance)
        
        # Create welcome notification
        Notification.objects.create(
            user=instance,
            title=_("Welcome to Our Platform!"),
            message=_("Thank you for joining us. Start earning by completing tasks and referring friends."),
            notification_type='welcome',
            priority='high'
        )



from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid


# class User(AbstractUser):
#     """Extended User model with earning platform specific fields"""
    
#     USER_TIER_CHOICES = [
#         ('FREE', 'Free'),
#         ('BRONZE', 'Bronze'),
#         ('SILVER', 'Silver'),
#         ('GOLD', 'Gold'),
#         ('PLATINUM', 'Platinum'),
#     ]
    
#     uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
#     balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
#     total_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
#     referral_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
#     referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='%(app_label)s_%(class)s_tenant')
#     tier = models.CharField(max_length=10, choices=USER_TIER_CHOICES, default='FREE', null=True, blank=True)
#     phone_number = models.CharField(max_length=20, null=True, blank=True)
#     country = models.CharField(max_length=100, null=True, blank=True)
#     is_verified = models.BooleanField(default=False)
#     verification_token = models.CharField(max_length=100, null=True, blank=True)
#     last_activity = models.DateTimeField(auto_now=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'users'
#         ordering = ['-created_at']
    
#     def __str__(self):
#         return f"{self.username} - ${self.balance}"
    
#     def generate_referral_code(self):
#         """Generate unique referral code"""
#         if not self.referral_code:
#             self.referral_code = f"EARN{str(uuid.uuid4())[:8].upper()}"
#             self.save()
#         return self.referral_code


class Wallet(models.Model):
    """User wallet for managing funds"""

    
    TRANSACTION_STATUS = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_wallet_user', null=True, blank=True)
    available_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    pending_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    lifetime_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    total_withdrawn = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wallets'
    
    def __str__(self):
        return f"{self.user.username}'s Wallet - ${self.available_balance}"
    
    def add_funds(self, amount, description=""):
        """Add funds to wallet"""
        self.available_balance = Decimal(str(self.available_balance)) + Decimal(str(amount))
        self.lifetime_earnings = Decimal(str(self.lifetime_earnings)) + Decimal(str(amount))
        self.save()
        
        Transaction.objects.create(
            user=self.user,
            amount=amount,
            transaction_type='CREDIT',
            description=description,
            status='COMPLETED'
        )
    
    def deduct_funds(self, amount, description=""):
        """Deduct funds from wallet"""
        if self.available_balance >= Decimal(str(amount)):
            self.available_balance -= Decimal(str(amount))
            self.save()
            
            Transaction.objects.create(
                user=self.user,
                amount=amount,
                transaction_type='DEBIT',
                description=description,
                status='COMPLETED'
            )
            return True
        return False


class Transaction(models.Model):
    """Transaction history"""

    
    TRANSACTION_TYPES = [
        ('CREDIT', 'Credit'),
        ('DEBIT', 'Debit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('REFUND', 'Refund'),
        ('REFERRAL', 'Referral Bonus'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_transaction_user', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, null=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', null=True, blank=True)
    reference_id = models.CharField(max_length=100, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='idx_user_created_at_036'),
            models.Index(fields=['status'], name='idx_status_037'),
            models.Index(fields=['transaction_type'], name='idx_transaction_type_038'),
        ]
    
    def __str__(self):
        return f"{self.transaction_type} - ${self.amount} - {self.user.username}"


class Offer(models.Model):
    """Available offers for users to complete"""

    
    OFFER_TYPES = [
        ('SURVEY', 'Survey'),
        ('APP_INSTALL', 'App Install'),
        ('VIDEO_AD', 'Video Ad'),
        ('GAME_TRIAL', 'Game Trial'),
        ('SIGNUP', 'Sign Up'),
        ('PURCHASE', 'Purchase'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('EXPIRED', 'Expired'),
    ]
    
    offer_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField()
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPES, null=True, blank=True)
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_time = models.IntegerField(help_text="Time in minutes")
    difficulty = models.CharField(max_length=20, choices=[('EASY', 'Easy'), ('MEDIUM', 'Medium'), ('HARD', 'Hard')], default='EASY')
    category = models.CharField(max_length=50, null=True, blank=True)
    featured = models.BooleanField(default=False)
    icon = models.CharField(max_length=10, default='[NOTE]', null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    terms = models.TextField(blank=True)
    max_completions = models.IntegerField(default=1)
    total_completions = models.IntegerField(default=0)
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', null=True, blank=True)
    countries = models.JSONField(default=list, blank=True)
    min_tier = models.CharField(max_length=10, default='FREE', null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'offers'
        ordering = ['-featured', '-reward_amount']
        indexes = [
            models.Index(fields=['status', 'offer_type'], name='idx_status_offer_type_039'),
            models.Index(fields=['featured'], name='idx_featured_040'),
        ]
    
    def __str__(self):
        return f"{self.title} - ${self.reward_amount}"
    
    def is_available_for_user(self, user):
        """Check if offer is available for specific user"""
        if self.status != 'ACTIVE':
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if user.country and self.countries and user.country not in self.countries:
            return False
        return True


class UserOffer(models.Model):
    """Track user's offer completions"""

    
    STATUS_CHOICES = [
        ('STARTED', 'Started'),
        ('PENDING', 'Pending Review'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_useroffer_user', null=True, blank=True)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='api_useroffer_offer', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='STARTED', null=True, blank=True)
    reward_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    proof_data = models.JSONField(default=dict, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'user_offers'
        unique_together = ['user', 'offer']
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_user_status_041'),
            models.Index(fields=['offer', 'status'], name='idx_offer_status_042'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.offer.title} - {self.status}"
    
    def complete(self):
        """Mark offer as completed and credit user"""
        if self.status != 'COMPLETED':
            self.status = 'COMPLETED'
            self.completed_at = timezone.now()
            self.reward_earned = self.offer.reward_amount
            self.save()
            
            # Credit user wallet
            wallet = self.user.wallet
            wallet.add_funds(
                self.reward_earned,
                f"Completed: {self.offer.title}"
            )
            
            # Update offer stats
            self.offer.total_completions += 1
            self.offer.save()
            
            return True
        return False


class Referral(models.Model):
    """Referral tracking and rewards"""

    
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_referral_referrer', null=True, blank=True)
    referred = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_referral_referred', null=True, blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=20.00, null=True, blank=True)
    total_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'referrals'
        unique_together = ['referrer', 'referred']
    
    def __str__(self):
        return f"{self.referrer.username} -> {self.referred.username}"
    
    def add_commission(self, amount):
        """Add referral commission"""
        if self.is_active:
            commission = Decimal(str(amount)) * (self.commission_rate / 100)
            self.total_earned += commission
            self.save()
            
            wallet = self.referrer.wallet
            wallet.add_funds(commission, f"Referral commission from {self.referred.username}")
            
            return commission
        return Decimal('0.00')


class DailyStats(models.Model):
    """Daily statistics for analytics"""

    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_dailystats_user', null=True, blank=True)
    date = models.DateField()
    clicks = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    offers_completed = models.IntegerField(default=0)
    time_spent = models.IntegerField(default=0, help_text="Time in minutes")
    
    class Meta:
        db_table = 'daily_stats'
        unique_together = ['user', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['user', '-date'], name='idx_user_date_043'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.date} - ${self.earnings}"


class Withdrawal(models.Model):
    """Withdrawal requests"""

    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PAYMENT_METHODS = [
        ('PAYPAL', 'PayPal'),
        ('BANK', 'Bank Transfer'),
        ('CRYPTO', 'Cryptocurrency'),
        ('MOBILE_MONEY', 'Mobile Money'),
    ]
    
    withdrawal_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_withdrawal_user', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, null=True, blank=True)
    payment_details = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', null=True, blank=True)
    processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    # processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='api_withdrawal_user')
    processed_by = models.ForeignKey(
    settings.AUTH_USER_MODEL, 
    on_delete=models.SET_NULL, 
    null=True, 
    blank=True, 
    related_name='api_withdrawal_processed_by'
)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'withdrawals'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_user_status_044'),
            models.Index(fields=['status'], name='idx_status_045'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - ${self.amount} - {self.status}"
    
    def approve(self, processed_by=None):
        """Approve withdrawal"""
        if self.status == 'PENDING':
            self.status = 'COMPLETED'
            self.processed_at = timezone.now()
            self.processed_by = processed_by
            self.save()
            
            # Deduct from wallet
            wallet = self.user.wallet
            wallet.deduct_funds(self.amount, f"Withdrawal: {self.withdrawal_id}")
            wallet.total_withdrawn += self.amount
            wallet.save()
            
            return True
        return False

# Notification
# class Notification(models.Model):

#     """User notifications"""
    
#     NOTIFICATION_TYPES = [
#         ('INFO', 'Information'),
#         ('SUCCESS', 'Success'),
#         ('WARNING', 'Warning'),
#         ('ERROR', 'Error'),
#         ('EARNING', 'Earning'),
#         ('WITHDRAWAL', 'Withdrawal'),
#     ]
    
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_withdrawal_tenant', null=True, blank=True)
#     notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='INFO', null=True, blank=True)
#     title = models.CharField(max_length=200, null=True, blank=True)
#     message = models.TextField()
#     icon = models.CharField(max_length=10, default='🔔', null=True, blank=True)
#     link = models.URLField(null=True, blank=True)
#     is_read = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         db_table = 'notifications'
#         ordering = ['-created_at']
#         indexes = [
#             models.Index(fields=['user', 'is_read'], name='idx_user_is_read_046'),
#         ]
    
#     def __str__(self):
#         return f"{self.user.username} - {self.title}"