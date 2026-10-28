# api/referral/models/advanced.py
# World-class missing features:
# QR codes, Geo rates, Sub-ID tracking, Double-sided bonus,
# Commission expiry, Attribution window, Recurring commission,
# Payout schedule preferences, Email invitations
# ============================================================

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


# ── 1. Sub-ID Tracking ────────────────────────────────────────────────────────

class ReferralSubID(models.Model):
    """
    PartnerStack-style Sub-ID tracking.
    Tracks which specific content/campaign/channel drove each referral.

    Example:
        /ref/EARN1234?sub1=youtube&sub2=tutorial_video&sub3=june_2024
        → tracks which YouTube video caused the most referrals
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_subid_tenant',
    )
    code = models.ForeignKey(
        'referral.ReferralCode', on_delete=models.CASCADE,
        related_name='sub_id_clicks',
    )
    # Up to 5 sub-ID parameters (like PartnerStack)
    sub1 = models.CharField(max_length=100, blank=True, default='')
    sub2 = models.CharField(max_length=100, blank=True, default='')
    sub3 = models.CharField(max_length=100, blank=True, default='')
    sub4 = models.CharField(max_length=100, blank=True, default='')
    sub5 = models.CharField(max_length=100, blank=True, default='')

    # Attribution
    click_ip     = models.GenericIPAddressField(null=True, blank=True)
    user_agent   = models.CharField(max_length=500, blank=True, default='')
    referrer_url = models.URLField(max_length=2000, blank=True, default='')
    landed_url   = models.URLField(max_length=2000, blank=True, default='')

    # Did this sub-ID lead to a conversion?
    converted        = models.BooleanField(default=False)
    conversion_time  = models.DateTimeField(null=True, blank=True)
    referred_user    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='subid_conversion',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code', 'sub1']),
            models.Index(fields=['converted']),
        ]

    def __str__(self):
        return f"SubID({self.code.code} sub1={self.sub1})"


# ── 2. Geo-Targeted Commission Rates ─────────────────────────────────────────

class GeoCommissionRate(models.Model):
    """
    Different commission rates per country.
    World #1 feature: US traffic gets 15%, BD gets 5% etc.
    Overrides default ReferralSettings rates for specific GEOs.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_geocommission_tenant',
    )
    # ISO 3166-1 alpha-2 country code
    country_code = models.CharField(
        max_length=2,
        help_text='ISO 3166-1 alpha-2 (US, GB, BD, IN etc.)',
    )
    country_name = models.CharField(max_length=100, blank=True, default='')

    level1_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    level2_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=5,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    level3_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # Which aspect does this apply to?
    applies_to = models.CharField(
        max_length=20,
        choices=[
            ('referrer', 'Referrer Location'),   # referrer is in this country
            ('referred', 'Referred User Location'),  # new user is in this country
            ('both', 'Either Party'),
        ],
        default='referred',
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        unique_together = ['tenant', 'country_code', 'applies_to']
        ordering = ['country_code']

    def __str__(self):
        return f"GeoRate({self.country_code}: L1={self.level1_rate}%)"


# ── 3. Commission Expiry / Time-Limited Commissions ──────────────────────────

class CommissionExpiryRule(models.Model):
    """
    CPAlead-style: earn 5% commission only for the first 6 months.
    After expiry_months, commission stops automatically.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_commexpiry_tenant',
    )
    name = models.CharField(max_length=200, default='Default Expiry Rule')

    # How long commissions last
    expiry_months    = models.IntegerField(
        default=0,
        help_text='0 = lifetime (no expiry). CPAlead uses 6 months.',
    )
    expiry_days      = models.IntegerField(default=0)
    expiry_earnings  = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Max total earnings per referral (0 = unlimited)',
    )

    # What happens after expiry?
    post_expiry_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Rate after expiry (0 = stop completely)',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']

    def __str__(self):
        if self.expiry_months:
            return f"Expiry({self.expiry_months} months then {self.post_expiry_rate}%)"
        return f"Expiry(lifetime {self.post_expiry_rate}%)"


class ReferralCommissionExpiry(models.Model):
    """
    Per-referral tracking of commission expiry.
    Created when a Referral is made. Expires automatically via Celery.
    """
    referral = models.OneToOneField(
        'referral.Referral', on_delete=models.CASCADE,
        related_name='commission_expiry',
    )
    rule = models.ForeignKey(
        CommissionExpiryRule, on_delete=models.SET_NULL, null=True, blank=True,
    )
    expires_at       = models.DateTimeField(null=True, blank=True)
    total_earned     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    earning_cap      = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_expired       = models.BooleanField(default=False)
    expired_at       = models.DateTimeField(null=True, blank=True)
    current_rate     = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'

    def is_commission_active(self) -> bool:
        from django.utils import timezone
        if self.is_expired:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.earning_cap and self.total_earned >= self.earning_cap:
            return False
        return True


# ── 4. Double-Sided Bonus ─────────────────────────────────────────────────────

class DoubleSidedBonusConfig(models.Model):
    """
    World best practice: BOTH referrer and referred user get a bonus.
    Referral Factory, ReferralCandy, Dropbox all use this.
    2x more conversions than single-sided programs (industry data).
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_doublesided_tenant',
    )
    name             = models.CharField(max_length=200, default='Double-Sided Signup Bonus')

    # Referrer bonus (already have this in ReferralSettings.referrer_signup_bonus)
    referrer_bonus   = models.DecimalField(max_digits=10, decimal_places=2, default=50)
    referrer_reward_type = models.CharField(
        max_length=15,
        choices=[('cash', 'Cash'), ('coins', 'Coins'), ('credits', 'Credits'), ('none', 'None')],
        default='cash',
    )

    # Referred user bonus (NEW — currently missing)
    referred_bonus   = models.DecimalField(max_digits=10, decimal_places=2, default=20)
    referred_reward_type = models.CharField(
        max_length=15,
        choices=[('cash', 'Cash'), ('coins', 'Coins'), ('credits', 'Credits'), ('none', 'None')],
        default='cash',
    )

    # Conditions
    min_activity_to_unlock = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Referred user must earn this much before bonus is unlocked for referrer',
    )
    valid_for_days  = models.IntegerField(
        default=0, help_text='0 = no time limit on referred user bonus claim',
    )

    # Display
    referrer_message = models.CharField(
        max_length=500, blank=True,
        default='You earned {amount} for referring {username}!',
    )
    referred_message = models.CharField(
        max_length=500, blank=True,
        default='Welcome! You got {amount} because {referrer} invited you.',
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        return f"DoubleSided(referrer={self.referrer_bonus}, referred={self.referred_bonus})"


# ── 5. Attribution Window Config ─────────────────────────────────────────────

class ReferralAttributionConfig(models.Model):
    """
    How long after clicking a referral link does the attribution last?
    PartnerStack: 90 days. Cookie tracking: 30 days by default.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_attribution_tenant',
    )
    cookie_window_days  = models.IntegerField(
        default=30,
        help_text='Cookie expiry (days). After this, referral link no longer attributed.',
    )
    session_window_days = models.IntegerField(
        default=1,
        help_text='Session-based attribution window (days).',
    )
    server_side_days    = models.IntegerField(
        default=90,
        help_text='Server-side (first-party) attribution window (days).',
    )
    last_click_wins     = models.BooleanField(
        default=True,
        help_text='If user clicks multiple referral links, last one wins.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'


# ── 6. Email Invitation ───────────────────────────────────────────────────────

class ReferralEmailInvitation(models.Model):
    """
    Email invitation system — referrer sends invite to friends.
    World #1 feature: Dropbox, Airbnb, PayPal all use email invites.
    """
    STATUS = [
        ('pending', 'Pending'), ('sent', 'Sent'),
        ('opened', 'Opened'), ('clicked', 'Clicked'),
        ('converted', 'Converted'), ('expired', 'Expired'),
        ('bounced', 'Bounced'), ('unsubscribed', 'Unsubscribed'),
    ]
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_emailinvite_tenant',
    )
    referrer       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sent_referral_invitations',
    )
    invited_email  = models.EmailField(db_index=True)
    invited_name   = models.CharField(max_length=200, blank=True, default='')
    referral_code  = models.ForeignKey(
        'referral.ReferralCode', on_delete=models.SET_NULL, null=True, blank=True,
    )

    personal_message = models.TextField(blank=True, default='')
    template_used    = models.CharField(max_length=100, blank=True, default='default')

    status       = models.CharField(max_length=15, choices=STATUS, default='pending')
    sent_at      = models.DateTimeField(null=True, blank=True)
    opened_at    = models.DateTimeField(null=True, blank=True)
    clicked_at   = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    expires_at   = models.DateTimeField(null=True, blank=True)

    # Tracking
    open_count   = models.IntegerField(default=0)
    click_count  = models.IntegerField(default=0)
    tracking_token = models.CharField(max_length=64, blank=True, unique=True)

    # Conversion
    converted_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='invitation_conversion',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']
        unique_together = ['referrer', 'invited_email']
        indexes = [
            models.Index(fields=['invited_email', 'status']),
            models.Index(fields=['tracking_token']),
        ]

    def __str__(self):
        return f"Invite({self.referrer.username} → {self.invited_email})"


# ── 7. Social Share Tracking ──────────────────────────────────────────────────

class ReferralSocialShare(models.Model):
    """
    Track social sharing — which platform drives most referrals?
    World #1: ReferralRock, Referral Factory all track this.
    """
    PLATFORMS = [
        ('whatsapp', 'WhatsApp'), ('telegram', 'Telegram'),
        ('facebook', 'Facebook'), ('twitter', 'Twitter/X'),
        ('instagram', 'Instagram'), ('tiktok', 'TikTok'),
        ('linkedin', 'LinkedIn'), ('sms', 'SMS'),
        ('email', 'Email'), ('copy_link', 'Copy Link'),
        ('qr_code', 'QR Code'), ('other', 'Other'),
    ]
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_socialshare_tenant',
    )
    referral_code = models.ForeignKey(
        'referral.ReferralCode', on_delete=models.CASCADE,
        related_name='social_shares',
    )
    platform     = models.CharField(max_length=15, choices=PLATFORMS)
    share_count  = models.PositiveIntegerField(default=0)
    click_count  = models.PositiveIntegerField(default=0)   # clicks from this share
    convert_count = models.PositiveIntegerField(default=0)  # conversions from this share
    last_shared  = models.DateTimeField(auto_now=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        unique_together = ['referral_code', 'platform']
        ordering = ['-share_count']

    def __str__(self):
        return f"Share({self.referral_code.code} on {self.platform})"


# ── 8. QR Code ────────────────────────────────────────────────────────────────

class ReferralQRCode(models.Model):
    """
    QR code for referral links.
    World #1 feature: ReferralRock, Referral Factory, Starbucks all have QR codes.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_qrcode_tenant',
    )
    referral_code  = models.OneToOneField(
        'referral.ReferralCode', on_delete=models.CASCADE,
        related_name='qr_code',
    )
    # Base64 encoded PNG QR image
    qr_image_data  = models.TextField(blank=True, default='')
    qr_url         = models.URLField(max_length=2000, blank=True, default='')

    # QR scan tracking
    scan_count     = models.PositiveIntegerField(default=0)
    last_scanned   = models.DateTimeField(null=True, blank=True)
    conversions    = models.PositiveIntegerField(default=0)

    # Customization
    foreground_color = models.CharField(max_length=7, default='#000000')
    background_color = models.CharField(max_length=7, default='#FFFFFF')
    include_logo     = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        return f"QR({self.referral_code.code})"

    def generate_qr(self, base_url: str = '') -> str:
        """Generate QR code as base64 PNG string."""
        try:
            import qrcode
            import base64
            from io import BytesIO

            referral_url = f"{base_url.rstrip('/')}/go/{self.referral_code.code}/"
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(referral_url)
            qr.make(fit=True)

            img = qr.make_image(
                fill_color=self.foreground_color,
                back_color=self.background_color,
            )
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            self.qr_image_data = f'data:image/png;base64,{b64}'
            self.save(update_fields=['qr_image_data', 'updated_at'])
            return self.qr_image_data
        except ImportError:
            # qrcode library not installed
            return ''
        except Exception:
            return ''


# ── 9. User Payout Preference ─────────────────────────────────────────────────

class UserPayoutPreference(models.Model):
    """
    User chooses their payout schedule — daily, weekly, monthly.
    CPAlead feature: flexible payout frequency per user.
    """
    SCHEDULE = [
        ('daily', 'Daily (min ৳100)'),
        ('weekly', 'Weekly (min ৳50)'),
        ('monthly', 'Monthly (min ৳20)'),
        ('manual', 'Manual Request'),
    ]
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_payoutpref_tenant',
    )
    user             = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='referral_payout_preference',
    )
    schedule         = models.CharField(max_length=10, choices=SCHEDULE, default='weekly')
    min_payout       = models.DecimalField(
        max_digits=10, decimal_places=2, default=50,
        help_text='Minimum amount before auto-payout triggers',
    )

    # Notification preferences
    notify_on_commission = models.BooleanField(default=True)
    notify_on_payout     = models.BooleanField(default=True)
    notify_on_milestone  = models.BooleanField(default=True)
    notify_weekly_summary = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        return f"PayoutPref({self.user.username}: {self.schedule})"


# ── 10. Recurring Commission Tracking ────────────────────────────────────────

class RecurringCommissionLog(models.Model):
    """
    Track recurring commissions (monthly subscription/deposit-based).
    Differs from one-time commissions — fires every month the user is active.
    """
    STATUS = [
        ('active', 'Active'), ('paused', 'Paused'),
        ('expired', 'Expired'), ('cancelled', 'Cancelled'),
    ]
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_recurringcomm_tenant',
    )
    referrer       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='recurring_commissions_earned',
    )
    referred_user  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='recurring_commissions_triggered',
    )
    level          = models.IntegerField(default=1)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5)

    # Recurring cycle
    cycle_months       = models.IntegerField(default=1)
    next_commission_at = models.DateTimeField(null=True, blank=True)
    last_paid_at       = models.DateTimeField(null=True, blank=True)
    total_paid         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_count      = models.IntegerField(default=0)

    # Limits
    max_payments   = models.IntegerField(default=0, help_text='0 = unlimited')
    expires_at     = models.DateTimeField(null=True, blank=True)

    status         = models.CharField(max_length=10, choices=STATUS, default='active')
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']
        unique_together = ['referrer', 'referred_user', 'level']

    def __str__(self):
        return f"Recurring({self.referrer.username} L{self.level} {self.commission_rate}%/month)"


# ── UTM Tracking ──────────────────────────────────────────────────────────────

class ReferralUTMSession(models.Model):
    """
    Store UTM parameters from the referral click.
    When a user registers via a referral link, these UTM params
    are attached to the referral for attribution.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_utmsession_tenant',
    )
    referral_code   = models.ForeignKey(
        'ReferralCode', on_delete=models.CASCADE,
        related_name='utm_sessions',
    )
    session_id      = models.CharField(max_length=64, db_index=True)
    utm_source      = models.CharField(max_length=200, blank=True, default='')
    utm_medium      = models.CharField(max_length=200, blank=True, default='')
    utm_campaign    = models.CharField(max_length=200, blank=True, default='')
    utm_term        = models.CharField(max_length=200, blank=True, default='')
    utm_content     = models.CharField(max_length=200, blank=True, default='')
    landing_url     = models.URLField(max_length=1000, blank=True, default='')
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    user_agent      = models.CharField(max_length=500, blank=True, default='')
    converted       = models.BooleanField(default=False, db_index=True)
    converted_user  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_utm_conversion',
    )
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)
    converted_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id', 'converted']),
        ]

    def __str__(self):
        return f"UTM({self.utm_source}/{self.utm_medium}/{self.utm_campaign})"


# ── Coupon / Promo Code Tracking ──────────────────────────────────────────────

class ReferralCoupon(models.Model):
    """
    Coupon-based referral tracking.
    User shares a coupon code (e.g. EARN20) instead of a URL.
    When someone uses the coupon, referral is attributed.
    Used by: CPAlead (promo codes), PartnerStack (coupon tracking).
    """
    DISCOUNT_TYPE = [
        ('percentage', 'Percentage (%)'),
        ('fixed',      'Fixed Amount'),
    ]
    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_coupon_tenant',
    )
    referral_code   = models.ForeignKey(
        'ReferralCode', on_delete=models.CASCADE,
        related_name='coupons',
    )
    coupon_code     = models.CharField(max_length=50, unique=True, db_index=True)
    discount_type   = models.CharField(max_length=10, choices=DISCOUNT_TYPE, default='percentage')
    discount_value  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_uses        = models.IntegerField(default=0, help_text='0 = unlimited')
    current_uses    = models.IntegerField(default=0)
    is_active       = models.BooleanField(default=True)
    expires_at      = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        return f"Coupon({self.coupon_code}: {self.discount_value}{'%' if self.discount_type=='percentage' else '৳'})"

    @property
    def is_valid(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True


# ── Multi-Touch Attribution ───────────────────────────────────────────────────

class ReferralAttributionTouch(models.Model):
    """
    Multi-touch attribution tracking.
    Records every referral touchpoint in a user's journey before conversion.
    Supports First-Click, Last-Click, and Linear attribution models.
    """
    TOUCH_TYPE = [
        ('first', 'First Touch'), ('last', 'Last Touch'),
        ('middle', 'Middle Touch'), ('direct', 'Direct Visit'),
    ]
    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_touch_tenant',
    )
    session_cookie  = models.CharField(max_length=100, db_index=True)
    referral_code   = models.ForeignKey(
        'ReferralCode', on_delete=models.CASCADE,
        related_name='attribution_touches', null=True, blank=True,
    )
    touch_type      = models.CharField(max_length=10, choices=TOUCH_TYPE)
    touch_order     = models.IntegerField(default=1)
    referrer_url    = models.URLField(max_length=1000, blank=True, default='')
    utm_source      = models.CharField(max_length=200, blank=True, default='')
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    converted       = models.BooleanField(default=False)
    converted_user  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_attribution_user',
    )
    weight          = models.DecimalField(
        max_digits=5, decimal_places=4, default=1,
        help_text='Attribution weight (0-1) for linear model',
    )
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'referral'
        ordering = ['session_cookie', 'touch_order']

    def __str__(self):
        return f"Touch({self.touch_type}:{self.touch_order}:{self.session_cookie[:8]})"


# ── Audience Segment ──────────────────────────────────────────────────────────

class ReferralAudienceSegment(models.Model):
    """
    Audience segmentation for targeted campaigns.
    Admin can create segments (e.g. "High LTV users", "New users <7 days")
    and apply different commission rules or bonuses per segment.
    """
    SEGMENT_TYPE = [
        ('user_age',       'User Age (days since joined)'),
        ('referral_count', 'Number of Referrals Made'),
        ('commission_total','Total Commission Earned'),
        ('ltv_category',   'LTV Category'),
        ('churn_risk',     'Churn Risk Level'),
        ('geo',            'Geographic Location'),
        ('custom',         'Custom Rule'),
    ]
    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_segment_tenant',
    )
    name            = models.CharField(max_length=200)
    description     = models.TextField(blank=True, default='')
    segment_type    = models.CharField(max_length=20, choices=SEGMENT_TYPE)
    condition_json  = models.JSONField(
        default=dict,
        help_text='e.g. {"min_ltv": 500, "max_churn_risk": "medium"}',
    )
    # Bonus for this segment
    commission_bonus_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    signup_bonus_extra   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active       = models.BooleanField(default=True)
    priority        = models.IntegerField(default=0)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-priority', '-created_at']

    def __str__(self):
        return f"Segment({self.name}: {self.segment_type})"


# ── Private / Invite-Only Campaign ────────────────────────────────────────────

class PrivateCampaignInvite(models.Model):
    """
    Private/invite-only campaign access control.
    Some campaigns are locked — only invited users can participate.
    e.g. VIP referral program for top 100 referrers only.
    """
    STATUS = [
        ('pending', 'Pending'), ('accepted', 'Accepted'),
        ('rejected', 'Rejected'), ('expired', 'Expired'),
    ]
    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_privateinvite_tenant',
    )
    campaign        = models.ForeignKey(
        'ReferralCampaign', on_delete=models.CASCADE,
        related_name='private_invites',
    )
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='private_campaign_invites',
    )
    invited_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sent_private_invites',
    )
    status          = models.CharField(max_length=10, choices=STATUS, default='pending')
    invite_token    = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at      = models.DateTimeField()
    created_at      = models.DateTimeField(auto_now_add=True)
    accepted_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'referral'
        unique_together = [('campaign', 'user')]

    def __str__(self):
        return f"PrivateInvite({self.user.username} → {self.campaign.name})"


# ── Custom Affiliate Fields ───────────────────────────────────────────────────

class AffiliateCustomField(models.Model):
    """
    Custom data fields per affiliate profile.
    Admin can define custom questions/fields for affiliate onboarding.
    e.g. "Monthly audience size", "Primary platform", "Country of operation"
    """
    FIELD_TYPE = [
        ('text', 'Text'), ('number', 'Number'),
        ('select', 'Select'), ('multiselect', 'Multi-Select'),
        ('boolean', 'Yes/No'), ('url', 'URL'),
    ]
    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_customfield_tenant',
    )
    field_key       = models.CharField(max_length=50, db_index=True)
    label           = models.CharField(max_length=200)
    field_type      = models.CharField(max_length=12, choices=FIELD_TYPE, default='text')
    options_json    = models.JSONField(default=list, blank=True)
    is_required     = models.BooleanField(default=False)
    display_order   = models.IntegerField(default=0)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['display_order']
        unique_together = [('tenant', 'field_key')]

    def __str__(self):
        return f"Field({self.field_key}: {self.field_type})"


class AffiliateCustomFieldValue(models.Model):
    """Value of a custom field for a specific affiliate."""
    affiliate       = models.ForeignKey(
        'AffiliateProfile', on_delete=models.CASCADE,
        related_name='custom_field_values',
    )
    field           = models.ForeignKey(
        AffiliateCustomField, on_delete=models.CASCADE,
        related_name='values',
    )
    value           = models.TextField(blank=True, default='')
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        unique_together = [('affiliate', 'field')]

    def __str__(self):
        return f"FieldVal({self.affiliate.user.username}.{self.field.field_key}={self.value[:20]})"


# ── Partner Contract / Terms ──────────────────────────────────────────────────

class PartnerContract(models.Model):
    """
    Digital contract/terms agreement between platform and affiliate.
    Affiliate must accept current terms before participating.
    """
    STATUS = [
        ('draft', 'Draft'), ('active', 'Active'), ('archived', 'Archived'),
    ]
    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_contract_tenant',
    )
    version         = models.CharField(max_length=20, db_index=True)
    title           = models.CharField(max_length=300)
    content         = models.TextField()
    summary         = models.TextField(blank=True, default='')
    status          = models.CharField(max_length=10, choices=STATUS, default='draft')
    effective_date  = models.DateField()
    requires_reaccept = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']

    def __str__(self):
        return f"Contract(v{self.version}: {self.title[:50]})"


class PartnerContractAcceptance(models.Model):
    """Record when an affiliate accepts the terms."""
    affiliate       = models.ForeignKey(
        'AffiliateProfile', on_delete=models.CASCADE,
        related_name='contract_acceptances',
    )
    contract        = models.ForeignKey(
        PartnerContract, on_delete=models.CASCADE,
        related_name='acceptances',
    )
    accepted_at     = models.DateTimeField(auto_now_add=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    signature_hash  = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        app_label = 'referral'
        unique_together = [('affiliate', 'contract')]

    def __str__(self):
        return f"Accept({self.affiliate.user.username}: v{self.contract.version})"


# ── A/B Test Campaign ─────────────────────────────────────────────────────────

class ReferralABTest(models.Model):
    """
    A/B testing for referral campaigns.
    Test different bonus amounts, messages, or landing pages.
    """
    STATUS = [('draft','Draft'),('running','Running'),('ended','Ended'),('winner_selected','Winner')]
    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_abtest_tenant',
    )
    name            = models.CharField(max_length=200)
    hypothesis      = models.TextField(blank=True, default='')
    status          = models.CharField(max_length=16, choices=STATUS, default='draft')
    traffic_split   = models.IntegerField(
        default=50, help_text='% of users in variant A (rest go to B)'
    )
    started_at      = models.DateTimeField(null=True, blank=True)
    ended_at        = models.DateTimeField(null=True, blank=True)
    winner_variant  = models.CharField(max_length=1, blank=True, default='',
                                        choices=[('A','A'),('B','B')])
    winner_rationale = models.TextField(blank=True, default='')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']

    def __str__(self):
        return f"ABTest({self.name}: {self.status})"


class ReferralABTestVariant(models.Model):
    """A or B variant configuration."""
    ab_test         = models.ForeignKey(
        ReferralABTest, on_delete=models.CASCADE,
        related_name='variants',
    )
    variant_name    = models.CharField(max_length=1, choices=[('A','A'),('B','B')])
    description     = models.CharField(max_length=300, blank=True, default='')
    referrer_bonus  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    referred_bonus  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    cta_text        = models.CharField(max_length=200, blank=True, default='')
    landing_page_url = models.URLField(blank=True, default='')
    # Metrics
    participants    = models.IntegerField(default=0)
    conversions     = models.IntegerField(default=0)
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        app_label = 'referral'
        unique_together = [('ab_test', 'variant_name')]

    @property
    def conversion_rate(self):
        if self.participants == 0:
            return 0.0
        return round(self.conversions / self.participants * 100, 2)

    def __str__(self):
        return f"Variant({self.ab_test.name}:{self.variant_name})"


# ── Reward Catalog ────────────────────────────────────────────────────────────

class ReferralRewardCatalog(models.Model):
    """
    Multiple reward types for referrals.
    Beyond cash — gift cards, product discounts, credits, swag.
    """
    REWARD_TYPE = [
        ('cash',        'Cash'),
        ('gift_card',   'Gift Card'),
        ('discount',    'Discount Code'),
        ('credits',     'Platform Credits'),
        ('product',     'Physical Product'),
        ('subscription','Subscription Extension'),
        ('badge',       'Digital Badge'),
    ]
    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_rewardcatalog_tenant',
    )
    name            = models.CharField(max_length=200)
    reward_type     = models.CharField(max_length=15, choices=REWARD_TYPE)
    description     = models.TextField(blank=True, default='')
    cash_value      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    image_url       = models.URLField(blank=True, default='')
    stock_available = models.IntegerField(default=0, help_text='0 = unlimited')
    stock_used      = models.IntegerField(default=0)
    is_active       = models.BooleanField(default=True)
    valid_from      = models.DateTimeField(null=True, blank=True)
    valid_until     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']

    @property
    def in_stock(self):
        return self.stock_available == 0 or self.stock_used < self.stock_available

    def __str__(self):
        return f"Reward({self.name}: {self.reward_type} ৳{self.cash_value})"


# ── Commission Split ──────────────────────────────────────────────────────────

class CommissionSplitRule(models.Model):
    """
    Split commission between multiple parties.
    e.g. Platform 20% + Referrer 80% of commission.
    Or: Content creator 40% + Direct referrer 60%.
    """
    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_splitsrule_tenant',
    )
    name            = models.CharField(max_length=200)
    is_active       = models.BooleanField(default=True)
    # Party A (usually the direct referrer)
    party_a_label   = models.CharField(max_length=100, default='Referrer')
    party_a_pct     = models.DecimalField(max_digits=5, decimal_places=2, default=80)
    # Party B (platform, sub-affiliate, or content creator)
    party_b_label   = models.CharField(max_length=100, default='Platform')
    party_b_pct     = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'

    @property
    def is_valid(self):
        return self.party_a_pct + self.party_b_pct == 100

    def __str__(self):
        return f"Split({self.party_a_pct}%/{self.party_b_pct}%: {self.name})"


# ── Tax Compliance ────────────────────────────────────────────────────────────

class AffiliateTaxInfo(models.Model):
    """
    Tax compliance information for affiliates.
    W-9 (US) / W-8BEN (international) / VAT number (EU).
    Required when affiliate earnings exceed reporting thresholds.
    """
    TAX_FORM_TYPE = [
        ('w9',        'W-9 (US Individual/Entity)'),
        ('w8ben',     'W-8BEN (Non-US Individual)'),
        ('w8bene',    'W-8BEN-E (Non-US Entity)'),
        ('vat',       'VAT Registration (EU)'),
        ('none',      'Not Required'),
    ]
    STATUS = [
        ('not_submitted', 'Not Submitted'),
        ('pending_review','Pending Review'),
        ('valid',         'Valid'),
        ('invalid',       'Invalid'),
        ('expired',       'Expired'),
    ]
    tenant                  = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_taxinfo_tenant',
    )
    affiliate               = models.OneToOneField(
        'AffiliateProfile', on_delete=models.CASCADE,
        related_name='tax_info',
    )
    tax_form_type           = models.CharField(max_length=10, choices=TAX_FORM_TYPE, default='none')
    status                  = models.CharField(max_length=15, choices=STATUS, default='not_submitted')
    taxpayer_id_encrypted   = models.CharField(max_length=500, blank=True, default='')
    vat_number              = models.CharField(max_length=50, blank=True, default='')
    country_of_residence    = models.CharField(max_length=2, blank=True, default='')
    annual_earnings         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reporting_threshold     = models.DecimalField(max_digits=10, decimal_places=2, default=600)
    requires_reporting      = models.BooleanField(default=False)
    submitted_at            = models.DateTimeField(null=True, blank=True)
    verified_at             = models.DateTimeField(null=True, blank=True)
    expires_at              = models.DateField(null=True, blank=True)
    notes                   = models.TextField(blank=True, default='')
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        return f"Tax({self.affiliate.user.username}: {self.tax_form_type} {self.status})"

    @property
    def needs_form(self):
        return self.annual_earnings >= self.reporting_threshold and self.status != 'valid'


# ── Mass Payout Batch ─────────────────────────────────────────────────────────

class MassPayoutBatch(models.Model):
    """
    Bulk commission payout processing.
    Admin creates a batch, reviews, then approves to send all at once.
    """
    STATUS = [
        ('draft', 'Draft'), ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'), ('processing', 'Processing'),
        ('completed', 'Completed'), ('failed', 'Failed'),
    ]
    tenant              = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_payoutbatch_tenant',
    )
    batch_name          = models.CharField(max_length=200)
    status              = models.CharField(max_length=18, choices=STATUS, default='draft')
    period_from         = models.DateField()
    period_to           = models.DateField()
    total_payouts       = models.IntegerField(default=0)
    total_amount        = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency            = models.CharField(max_length=3, default='BDT')
    payment_method      = models.CharField(
        max_length=20,
        choices=[('bkash','bKash'),('nagad','Nagad'),('bank','Bank Transfer'),
                 ('paypal','PayPal'),('crypto','Crypto')],
        default='bkash',
    )
    created_by          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_mass_payout_batches_created',
    )
    approved_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_mass_payout_batches_approved',
    )
    processed_at        = models.DateTimeField(null=True, blank=True)
    notes               = models.TextField(blank=True, default='')
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']

    def __str__(self):
        return f"Batch({self.batch_name}: ৳{self.total_amount} {self.status})"


class MassPayoutBatchItem(models.Model):
    """Individual payout within a batch."""
    STATUS = [
        ('pending','Pending'),('paid','Paid'),
        ('failed','Failed'),('skipped','Skipped'),
    ]
    batch               = models.ForeignKey(
        MassPayoutBatch, on_delete=models.CASCADE,
        related_name='items',
    )
    user                = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='payout_batch_items',
    )
    amount              = models.DecimalField(max_digits=12, decimal_places=2)
    payment_account     = models.CharField(max_length=200, blank=True, default='')
    payment_method      = models.CharField(max_length=20, blank=True, default='')
    status              = models.CharField(max_length=10, choices=STATUS, default='pending')
    transaction_id      = models.CharField(max_length=200, blank=True, default='')
    error_message       = models.TextField(blank=True, default='')
    processed_at        = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-amount']

    def __str__(self):
        return f"PayoutItem({self.user.username}: ৳{self.amount} {self.status})"


# ── CCPA Compliance ───────────────────────────────────────────────────────────

class CCPARequest(models.Model):
    """
    CCPA (California Consumer Privacy Act) requests.
    Right to know, right to delete, right to opt-out of sale.
    """
    REQUEST_TYPE = [
        ('know',        'Right to Know'),
        ('delete',      'Right to Delete'),
        ('optout_sale', 'Opt-Out of Sale'),
        ('optout_share','Opt-Out of Share'),
    ]
    STATUS = [
        ('received','Received'),('processing','Processing'),
        ('completed','Completed'),('denied','Denied'),
    ]
    user                = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='ccpa_requests',
    )
    request_type        = models.CharField(max_length=12, choices=REQUEST_TYPE)
    status              = models.CharField(max_length=10, choices=STATUS, default='received')
    submitted_at        = models.DateTimeField(auto_now_add=True)
    completed_at        = models.DateTimeField(null=True, blank=True)
    response_notes      = models.TextField(blank=True, default='')
    verification_code   = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        app_label = 'referral'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"CCPA({self.user.username}: {self.request_type} {self.status})"


# ── Custom Domain ─────────────────────────────────────────────────────────────

class ReferralCustomDomain(models.Model):
    """
    Custom domain mapping for referral links.
    e.g. earn.yourplatform.com/go/CODE instead of yourplatform.com/referral/go/CODE
    """
    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_customdomain_tenant',
    )
    domain          = models.CharField(max_length=255, unique=True, db_index=True)
    is_verified     = models.BooleanField(default=False)
    is_active       = models.BooleanField(default=False)
    dns_txt_record  = models.CharField(max_length=200, blank=True, default='')
    ssl_enabled     = models.BooleanField(default=False)
    verified_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'

    @property
    def full_go_url(self):
        scheme = 'https' if self.ssl_enabled else 'http'
        return f'{scheme}://{self.domain}/go/'

    def __str__(self):
        return f"Domain({self.domain}: {'✅' if self.is_verified else '⏳'})"


# ── VPN/Proxy Detection Log ───────────────────────────────────────────────────

class VPNDetectionLog(models.Model):
    """
    Log VPN/proxy detections.
    High VPN usage is a fraud signal.
    """
    ip_address          = models.GenericIPAddressField(db_index=True)
    is_vpn              = models.BooleanField(default=False)
    is_proxy            = models.BooleanField(default=False)
    is_tor              = models.BooleanField(default=False)
    is_datacenter       = models.BooleanField(default=False)
    country_code        = models.CharField(max_length=2, blank=True, default='')
    detection_source    = models.CharField(
        max_length=50, default='rule_based',
        choices=[('rule_based','Rule-Based'),('api','External API'),('ml','ML Model')],
    )
    fraud_score_added   = models.IntegerField(default=0)
    detected_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-detected_at']
        indexes = [models.Index(fields=['ip_address', 'is_vpn'])]

    def __str__(self):
        flags = []
        if self.is_vpn: flags.append('VPN')
        if self.is_proxy: flags.append('Proxy')
        if self.is_tor: flags.append('Tor')
        return f"VPNLog({self.ip_address}: {'/'.join(flags) or 'Clean'})"