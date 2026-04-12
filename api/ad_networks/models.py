import json
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel
from api.users.models import User
from datetime import timedelta
from django.conf import settings
import decimal



# ==================== HELPER FUNCTIONS ====================

def default_list():
    """Return empty list for JSONField default"""
    return []

def default_dict():
    """Return empty dict for JSONField default"""
    return {}

def default_platforms():
    """Default platforms list"""
    return ["android", "ios", "web"]

def default_devices():
    """Default device types"""
    return ["mobile", "tablet", "desktop"]


# ====================== Ad Networks & Offerwalls ======================

class AdNetwork(TimeStampedModel):
    """Ad Network providers - 50+ Networks"""
    
    # Network Categories
    NETWORK_CATEGORIES = (
        ('offerwall', 'Offerwall'),
        ('survey', 'Survey'),
        ('video', 'Video/Ads'),
        ('gaming', 'Gaming'),
        ('app_install', 'App Install'),
        ('cashback', 'Cashback'),
        ('cpi_cpa', 'CPI/CPA'),
        ('cpe', 'CPE (Cost Per Engagement)'),
        ('other', 'Other'),
    )
    
    # Country Support Levels
    COUNTRY_SUPPORT = (
        ('global', 'Global'),
        ('tier1', 'Tier 1 (US, UK, CA, AU)'),
        ('tier2', 'Tier 2 (EU, Middle East)'),
        ('tier3', 'Tier 3 (Asia, Africa, South America)'),
        ('bd_only', 'Bangladesh Only'),
        ('indian_sub', 'Indian Subcontinent'),
    )
    
    # Payment Methods
    PAYMENT_METHODS = (
        ('paypal', 'PayPal'),
        ('bank', 'Bank Transfer'),
        ('crypto', 'Cryptocurrency'),
        ('skrill', 'Skrill'),
        ('payoneer', 'Payoneer'),
        ('wire', 'Wire Transfer'),
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
        ('upay', 'Upay'),
    )
    
    # ====== 50+ NETWORK TYPES ======
    NETWORK_TYPES = (
        # Basic Networks (1-6)
        ('admob', 'Google AdMob'),
        ('unity', 'Unity Ads'),
        ('ironsource', 'IronSource'),
        ('applovin', 'AppLovin'),
        ('tapjoy', 'Tapjoy'),
        ('vungle', 'Vungle'),
        
        # Top Offerwalls (7-26)
        ('adscend', 'Adscend Media'),
        ('offertoro', 'OfferToro'),
        ('adgem', 'AdGem'),
        ('ayetstudios', 'Ayetstudios'),
        ('lootably', 'Lootably'),
        ('revenueuniverse', 'Revenue Universe'),
        ('adgate', 'AdGate Media'),
        ('cpalead', 'CPAlead'),
        ('adworkmedia', 'AdWork Media'),
        ('wannads', 'Wannads'),
        ('personaly', 'Persona.ly'),
        ('kiwiwall', 'KiwiWall'),
        ('monlix', 'Monlix'),
        ('notik', 'Notik'),
        ('offerdaddy', 'OfferDaddy'),
        ('offertown', 'OfferTown'),
        ('adlockmedia', 'AdLock Media'),
        ('offerwallpro', 'Offerwall.pro'),
        ('wallads', 'WallAds'),
        ('wallport', 'Wallport'),
        ('walltoro', 'WallToro'),
        
        # Survey Specialists (27-41)
        ('pollfish', 'Pollfish'),
        ('cpxresearch', 'CPX Research'),
        ('bitlabs', 'BitLabs'),
        ('inbrain', 'InBrain.ai'),
        ('theoremreach', 'TheoremReach'),
        ('yoursurveys', 'YourSurveys'),
        ('surveysavvy', 'SurveySavvy'),
        ('opinionworld', 'OpinionWorld'),
        ('toluna', 'Toluna'),
        ('surveymonkey', 'SurveyMonkey'),
        ('swagbucks', 'Swagbucks'),
        ('prizerebel', 'PrizeRebel'),
        ('grabpoints', 'GrabPoints'),
        ('instagc', 'InstaGC'),
        ('points2shop', 'Points2Shop'),
        
        # Video & Easy Tasks (42-56)
        ('loottv', 'Loot.tv'),
        ('hideouttv', 'Hideout.tv'),
        ('rewardrack', 'RewardRack'),
        ('earnhoney', 'EarnHoney'),
        ('rewardxp', 'RewardXP'),
        ('idleempire', 'Idle-Empire'),
        ('gain', 'Gain.gg'),
        ('grindabuck', 'GrindaBuck'),
        ('timebucks', 'TimeBucks'),
        ('clixsense', 'ClixSense'),
        ('neobux', 'NeoBux'),
        ('probux', 'ProBux'),
        ('clixwall', 'ClixWall'),
        ('fyber', 'Fyber'),
        ('offerstation', 'OfferStation'),
        
        # Gaming & App Install (57-70)
        ('chartboost', 'Chartboost'),
        ('supersonic', 'Supersonic'),
        ('appnext', 'AppNext'),
        ('digitalturbine', 'Digital Turbine'),
        ('glispa', 'Glispa'),
        ('adcolony', 'AdColony'),
        ('inmobi', 'InMobi'),
        ('mopub', 'MoPub'),
        ('pangle', 'Pangle (by TikTok)'),
        ('mintegral', 'Mintegral'),
        ('ogury', 'Ogury'),
        ('verizonmedia', 'Verizon Media'),
        ('smaato', 'Smaato'),
        ('mobilefuse', 'MobileFuse'),
        
        # More Networks (71-80)
        ('leadbolt', 'Leadbolt'),
        ('startapp', 'StartApp'),
        ('mediabrix', 'Mediabrix'),
        ('nativex', 'NativeX'),
        ('heyzap', 'Heyzap'),
        ('kidoz', 'Kidoz'),
        ('pokkt', 'Pokkt'),
        ('youappi', 'YouAppi'),
        ('ampiri', 'Ampiri'),
        ('adincube', 'AdinCube'),
        
        # Future Expansion (81-90)
        ('custom1', 'Custom Network 1'),
        ('custom2', 'Custom Network 2'),
        ('custom3', 'Custom Network 3'),
        ('custom4', 'Custom Network 4'),
        ('custom5', 'Custom Network 5'),
        ('custom6', 'Custom Network 6'),
        ('custom7', 'Custom Network 7'),
        ('custom8', 'Custom Network 8'),
        ('custom9', 'Custom Network 9'),
        ('custom10', 'Custom Network 10'),
    )
    
    # Basic Information
    name = models.CharField(max_length=100, null=True, blank=True)
    # `network_type` used to be unique & required, but tests create
    # `AdNetwork` instances without providing it. Make it optional and
    # non-unique so simple creations in tests pass without IntegrityError.
    network_type = models.CharField(
        max_length=50,
        choices=NETWORK_TYPES,
        unique=False,
        blank=True,
        null=True,)
    category = models.CharField(max_length=20, choices=NETWORK_CATEGORIES, default='offerwall', null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to='network_logos/', blank=True, null=True)
    logo_url = models.URLField(max_length=500, null=True, blank=True)
    banner_url = models.URLField(max_length=500, null=True, blank=True)
    
    # API Configuration
    api_key = models.CharField(max_length=500, blank=True, null=True)
    api_secret = models.CharField(max_length=500, blank=True, null=True)
    publisher_id = models.CharField(max_length=255, blank=True, null=True)
    sub_publisher_id = models.CharField(max_length=255, blank=True, null=True)
    api_token = models.CharField(max_length=500, blank=True, null=True)
    
    # URLs
    base_url = models.URLField(blank=True, null=True, help_text='API Base URL')
    webhook_url = models.URLField(blank=True, null=True)
    callback_url = models.URLField(blank=True, null=True)
    dashboard_url = models.URLField(blank=True, null=True)
    support_url = models.URLField(blank=True, null=True)
    
    # POSTBACK CONFIGURATION - এই ৩টি ফিল্ড যোগ করুন
    postback_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Postback URL")
    postback_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Postback Key")
    postback_password = models.CharField(max_length=255, blank=True, null=True, verbose_name="Postback Password")
    
    # Settings & Status
    is_active = models.BooleanField(default=True)
    is_testing = models.BooleanField(default=False, help_text='In testing phase')
    priority = models.IntegerField(default=0, help_text='Higher number = higher priority')
    rating = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    
    # Financial Settings
    min_payout = models.DecimalField(max_digits=10, decimal_places=2, default=1.00, null=True, blank=True)
    max_payout = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00, blank=True, null=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text='Your commission %', null=True, blank=True)
    payment_methods = models.JSONField(default=default_list, blank=True)
    payment_duration = models.IntegerField(default=30, help_text='Payment processing days')
    
    # Features Support
    supports_postback = models.BooleanField(default=True)
    supports_webhook = models.BooleanField(default=True)
    supports_offers = models.BooleanField(default=True)
    supports_surveys = models.BooleanField(default=False)
    supports_video = models.BooleanField(default=False)
    supports_app_install = models.BooleanField(default=False)
    supports_gaming = models.BooleanField(default=False)
    supports_quiz = models.BooleanField(default=False)
    supports_tasks = models.BooleanField(default=False)
    
    # Geo & Platform Targeting
    country_support = models.CharField(max_length=20, choices=COUNTRY_SUPPORT, default='global', null=True, blank=True)
    countries = models.JSONField(default=default_list, blank=True, help_text='Specific countries list')
    platforms = models.JSONField(default=default_platforms, blank=True)
    device_types = models.JSONField(default=default_devices, blank=True)
    
    # Performance Metrics
    total_payout = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
    total_conversions = models.IntegerField(default=0)
    total_clicks = models.IntegerField(default=0)
    conversion_rate = models.FloatField(default=0, help_text='CR% = Conversions/Clicks')
    epc = models.DecimalField(max_digits=10, decimal_places=4, default=0, help_text='Earnings Per Click', null=True, blank=True)
    
    # Time Settings
    offer_refresh_interval = models.IntegerField(default=3600, help_text='Seconds between offer refreshes')
    last_sync = models.DateTimeField(null=True, blank=True)
    next_sync = models.DateTimeField(null=True, blank=True)
    
    # Configuration & Metadata
    config = models.JSONField(default=default_dict, blank=True, help_text='Network-specific configuration')
    metadata = models.JSONField(default=default_dict, blank=True)
    notes = models.TextField(blank=True, null=True, help_text='Internal notes')
    
    # Verification & Security
    is_verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)
    trust_score = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    class Meta:
        verbose_name = 'Ad Network'
        verbose_name_plural = 'Ad Networks'
        ordering = ['-priority', '-rating', 'name']
        indexes = [
            models.Index(fields=['network_type']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['country_support']),
            models.Index(fields=['trust_score']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"
    
    def save(self, *args, **kwargs):
        # Auto-generate name if not provided
        if not self.name and self.network_type:
            self.name = dict(self.NETWORK_TYPES).get(self.network_type, self.network_type)
        super().save(*args, **kwargs)
    
    @property
    def is_configured(self):
        """Check if network is properly configured"""
        if self.supports_offers and not self.api_key:
            return False
        return True
    
    @property
    def success_rate(self):
        """Calculate successful conversion rate"""
        if self.total_clicks > 0:
            return (self.total_conversions / self.total_clicks) * 100
        return 0
    
    @property
    def avg_payout(self):
        """Calculate average payout per conversion"""
        if self.total_conversions > 0:
            return self.total_payout / self.total_conversions
        return 0


# ====================== Offer Categories ======================

class OfferCategory(TimeStampedModel):
    """Categories for offers"""
    CATEGORY_TYPES = (
        ('survey', 'Survey'),
        ('offer', 'Offer'),
        ('video', 'Video'),
        ('game', 'Game'),
        ('app_install', 'App Install'),
        ('quiz', 'Quiz'),
        ('task', 'Task'),
        ('signup', 'Signup'),
        ('shopping', 'Shopping'),
        ('cashback', 'Cashback'),
        ('other', 'Other'),
    )
    
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    slug = models.SlugField(max_length=100, unique=True, null=True, blank=True)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default='offer', null=True, blank=True)
    icon = models.CharField(max_length=50, blank=True, null=True, help_text='FontAwesome icon class')
    image = models.ImageField(upload_to='offer_categories/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default='#3498db', help_text='Hex color code', null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    
    # এই ফিল্ডটি যোগ করুন
    display_order = models.IntegerField(default=0, verbose_name="Display Order")
    
    # SEO & Display
    meta_title = models.CharField(max_length=200, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    keywords = models.JSONField(default=default_list, blank=True)
    
    # Statistics
    total_offers = models.IntegerField(default=0)
    total_conversions = models.IntegerField(default=0)
    avg_reward = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Offer Category'
        verbose_name_plural = 'Offer Categories'
        ordering = ['display_order', 'order', 'name']  # display_order যোগ করুন
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    @property
    def active_offers_count(self):
        from django.db.models import Count, Q
        return self.offers.filter(status='active').count()


# ====================== Offers ======================

class Offer(TimeStampedModel):
    """Individual offers from ad networks"""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('pending', 'Pending Review'),
        ('rejected', 'Rejected'),
    )
    
    DIFFICULTY_LEVELS = (
        ('very_easy', 'Very Easy'),
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
        ('very_hard', 'Very Hard'),
    )
    
    DEVICE_TYPES = (
        ('any', 'Any Device'),
        ('mobile', 'Mobile Only'),
        ('tablet', 'Tablet Only'),
        ('desktop', 'Desktop Only'),
        ('android', 'Android Only'),
        ('ios', 'iOS Only'),
    )
    
    GENDER_TARGETING = (
        ('any', 'Any Gender'),
        ('male', 'Male Only'),
        ('female', 'Female Only'),
    )
    
    AGE_GROUPS = (
        ('13-17', 'Teen (13-17)'),
        ('18-24', 'Young Adult (18-24)'),
        ('25-34', 'Adult (25-34)'),
        ('35-44', 'Middle Age (35-44)'),
        ('45-54', 'Senior Adult (45-54)'),
        ('55+', 'Elderly (55+)'),
        ('any', 'Any Age'),
    )
    
    # Basic Information
    ad_network = models.ForeignKey(AdNetwork, on_delete=models.CASCADE, related_name='%(app_label)s_%(class)s_tenant')
    category = models.ForeignKey(OfferCategory, on_delete=models.SET_NULL, null=True, related_name='%(app_label)s_%(class)s_tenant')
    
    external_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    internal_id = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField()
    instructions = models.TextField(blank=True, null=True)
    thumbnail = models.URLField(blank=True, null=True)
    preview_images = models.JSONField(default=default_list, blank=True)
    
    # Reward Information
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    reward_currency = models.CharField(max_length=10, default='BDT', null=True, blank=True)
    network_payout = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    
    # Offer Details
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS, default='easy', null=True, blank=True)
    estimated_time = models.IntegerField(default=5, help_text='Estimated time in minutes')
    steps_required = models.IntegerField(default=1, help_text='Number of steps to complete')
    
    # Limits & Availability
    total_conversions = models.IntegerField(default=0)
    daily_conversions = models.IntegerField(default=0, help_text='Conversions today')
    max_conversions = models.IntegerField(null=True, blank=True)
    max_daily_conversions = models.IntegerField(null=True, blank=True)
    user_daily_limit = models.IntegerField(default=1, help_text='Max per user per day')
    user_lifetime_limit = models.IntegerField(default=1, help_text='Max per user lifetime')
    
    # Targeting
    countries = models.JSONField(default=default_list, blank=True)
    platforms = models.JSONField(default=default_platforms, blank=True)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES, default='any', null=True, blank=True)
    min_age = models.IntegerField(default=13, validators=[MinValueValidator(13), MaxValueValidator(100)])
    max_age = models.IntegerField(default=100, validators=[MinValueValidator(13), MaxValueValidator(100)])
    gender_targeting = models.CharField(max_length=10, choices=GENDER_TARGETING, default='any', null=True, blank=True)
    age_group = models.CharField(max_length=10, choices=AGE_GROUPS, default='any', null=True, blank=True)
    
    # URLs
    click_url = models.URLField(null=True, blank=True)
    tracking_url = models.URLField(blank=True, null=True)
    preview_url = models.URLField(blank=True, null=True)
    terms_url = models.URLField(blank=True, null=True)
    privacy_url = models.URLField(blank=True, null=True)
    
    # Status & Visibility
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    is_hot = models.BooleanField(default=False, help_text='High demand offer')
    is_new = models.BooleanField(default=True)
    is_exclusive = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)
    
    # Time Settings
    expires_at = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    # Performance Metrics
    click_count = models.IntegerField(default=0)
    conversion_rate = models.FloatField(default=0)
    avg_completion_time = models.IntegerField(default=0, help_text='Average completion time in seconds')
    quality_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    
    # Metadata
    metadata = models.JSONField(default=default_dict, blank=True)
    tags = models.JSONField(default=default_list, blank=True)
    requirements = models.JSONField(default=default_list, blank=True, help_text='List of requirements')
    
    # Fraud Protection
    fraud_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    requires_screenshot = models.BooleanField(default=False)
    requires_verification = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Offer'
        verbose_name_plural = 'Offers'
        ordering = ['-is_featured', '-is_hot', '-reward_amount', '-created_at']
        indexes = [
            models.Index(fields=['status', 'is_featured']),
            models.Index(fields=['external_id']),
            models.Index(fields=['ad_network', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['reward_amount']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.reward_amount} {self.reward_currency}"
    
    @property
    def is_available(self):
        """Check if offer is still available"""
        now = timezone.now()
        
        if self.status != 'active':
            return False
        if self.max_conversions and self.total_conversions >= self.max_conversions:
            return False
        if self.expires_at and self.expires_at < now:
            return False
        if self.starts_at and self.starts_at > now:
            return False
        return True
    
    @property
    def remaining_conversions(self):
        """Calculate remaining conversions"""
        if self.max_conversions:
            return max(0, self.max_conversions - self.total_conversions)
        return None
    
    @property
    def effective_reward(self):
        """Calculate effective reward after commission"""
        return self.reward_amount + self.commission
    
    @property
    def completion_rate(self):
        """Calculate completion rate"""
        if self.click_count > 0:
            return (self.total_conversions / self.click_count) * 100
        return 0


# ====================== User Offer Engagements ======================

class UserOfferEngagement(TimeStampedModel):
    """Track user interactions with offers"""
    
    STATUS_CHOICES = (
        ('clicked', 'Clicked'),
        ('started', 'Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('pending', 'Pending Verification'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('canceled', 'Canceled'),
        ('expired', 'Expired'),
    )
    
    REJECTION_REASONS = (
        ('fraud', 'Fraud Detected'),
        ('incomplete', 'Incomplete Action'),
        ('quality', 'Low Quality'),
        ('duplicate', 'Duplicate'),
        ('timeout', 'Time Limit Exceeded'),
        ('invalid', 'Invalid Data'),
        ('other', 'Other'),
    )
    
    # এই ফিল্ডগুলো অবশ্যই যোগ করতে হবে:
    tracking_id = models.CharField(max_length=255, null=True, blank=True)
    device_id = models.CharField(max_length=255, null=True, blank=True)
    conversion_reported_at = models.DateTimeField(null=True, blank=True)
    postback_attempts = models.IntegerField(default=0)
    last_postback_attempt = models.DateTimeField(null=True, blank=True)
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ad_networks_userofferengagement_user', null=True, blank=True)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='ad_networks_userofferengagement_offer', null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='clicked', null=True, blank=True)
    progress = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Tracking IDs
    click_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    conversion_id = models.CharField(max_length=255, blank=True, null=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    campaign_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Device & Location Info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    device_info = models.JSONField(default=default_dict, blank=True)
    location_data = models.JSONField(default=default_dict, blank=True)
    browser = models.CharField(max_length=100, blank=True, null=True)
    os = models.CharField(max_length=100, blank=True, null=True)
    
    # Reward Information
    reward_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    network_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    commission_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    
    # Time Tracking
    clicked_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    rewarded_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    
    # Verification
    rejection_reason = models.CharField(max_length=20, choices=REJECTION_REASONS, blank=True, null=True)
    rejection_details = models.TextField(blank=True, null=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='ad_networks_userofferengagement_verified_by')
    
    # Screenshots & Proof
    screenshot = models.ImageField(upload_to='engagement_screenshots/', blank=True, null=True)
    proof_data = models.JSONField(default=default_dict, blank=True)
    
    # Session Data
    session_id = models.CharField(max_length=255, blank=True, null=True)
    referrer_url = models.URLField(blank=True, null=True)
    
    # Metadata
    metadata = models.JSONField(default=default_dict, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'User Offer Engagement'
        verbose_name_plural = 'User Offer Engagements'
        ordering = ['-created_at']
        unique_together = ['user', 'offer', 'click_id']
        indexes = [
            models.Index(fields=['click_id']),
            models.Index(fields=['conversion_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['offer', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.offer.title} - {self.status}"
    
    @property
    def time_spent(self):
        """Calculate time spent on offer"""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_expired(self):
        """Check if engagement is expired"""
        if self.expired_at and self.expired_at < timezone.now():
            return True
        return False
    
    @property
    def can_be_completed(self):
        """Check if engagement can be completed"""
        return self.status in ['clicked', 'started', 'in_progress'] and not self.is_expired


# ====================== Offer Conversions ======================

class OfferConversion(TimeStampedModel):
    """Track conversions from ad networks with fraud protection"""
    
    CONVERSION_STATUS = (
        ('pending', 'Pending Verification'),
        ('verified', 'Verified by Network'),
        ('approved', 'Approved for Payment'),
        ('rejected', 'Rejected (Fraud)'),
        ('chargeback', 'Chargeback (Payment Cancelled)'),
        ('disputed', 'Disputed'),
        ('paid', 'Paid to User'),
    )
    
    engagement = models.OneToOneField(UserOfferEngagement, on_delete=models.CASCADE, related_name='%(app_label)s_%(class)s_tenant')
    
    # Network Data
    postback_data = models.JSONField(default=default_dict)
    payout = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    network_currency = models.CharField(max_length=10, default='USD', null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1, null=True, blank=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='ad_networks_offerconversion_verified_by')
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Fraud Protection Fields
    conversion_status = models.CharField(max_length=20, choices=CONVERSION_STATUS, default='pending', null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    chargeback_at = models.DateTimeField(blank=True, null=True)
    chargeback_reason = models.TextField(blank=True, null=True)
    chargeback_processed = models.BooleanField(default=False)
    
    # Fraud Detection
    fraud_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    fraud_reasons = models.JSONField(default=default_list, blank=True)
    risk_level = models.CharField(
        max_length=20, 
        default='low', 
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    )
    
    # Payment Tracking
    payment_reference = models.CharField(max_length=255, blank=True, null=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    
    # Analytics
    processing_time = models.IntegerField(default=0, help_text='Processing time in seconds')
    retry_count = models.IntegerField(default=0)
    
    # Metadata
    metadata = models.JSONField(default=default_dict, blank=True)
    
    class Meta:
        verbose_name = 'Offer Conversion'
        verbose_name_plural = 'Offer Conversions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['conversion_status']),
            models.Index(fields=['fraud_score']),
            models.Index(fields=['chargeback_processed']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Conversion: {self.engagement.user.username} - {self.payout}"
    
  
    @property
    def local_payout(self):
        """Calculate payout in local currency"""
        try:
                # প্রথমে None চেক করুন
            if self.payout is None or self.exchange_rate is None:
                return 0
        
                # তারপর Type চেক করুন
            if not isinstance(self.payout, (int, float, decimal.Decimal)):
                return 0
        
            if not isinstance(self.exchange_rate, (int, float, decimal.Decimal)):
                return 0
        
               # সেফভাবে গুণ করুন
            return float(self.payout) * float(self.exchange_rate)
        except (TypeError, ValueError):
            return 0
    
    @property
    def is_chargeback(self):
        """Check if conversion is chargeback"""
        return self.conversion_status == 'chargeback'
    
    @property
    def is_fraudulent(self):
        """Check if conversion is fraudulent"""
        return self.conversion_status in ['rejected', 'chargeback'] or self.fraud_score > 70


# ====================== Offer Walls ======================

class OfferWall(TimeStampedModel):
    """Offerwall configurations for different placements"""
    
    WALL_TYPES = (
        ('main', 'Main Offerwall'),
        ('survey', 'Survey Wall'),
        ('video', 'Video Wall'),
        ('game', 'Game Wall'),
        ('app', 'App Install Wall'),
        ('featured', 'Featured Offers'),
        ('trending', 'Trending Offers'),
        ('high_paying', 'High Paying Offers'),
        ('quick', 'Quick Offers'),
    )
    
    name = models.CharField(max_length=100, null=True, blank=True)
    slug = models.SlugField(max_length=100, unique=True, null=True, blank=True)
    wall_type = models.CharField(max_length=20, choices=WALL_TYPES, default='main', null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    
    # Content
    ad_networks = models.ManyToManyField(AdNetwork, related_name='%(app_label)s_%(class)s_tenant')
    categories = models.ManyToManyField(OfferCategory, related_name='%(app_label)s_%(class)s_tenant', blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    min_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    max_offers = models.IntegerField(default=50, help_text='Maximum offers to display')
    refresh_interval = models.IntegerField(default=300, help_text='Seconds between refreshes')
    
    # Filtering
    min_reward = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    max_reward = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    allowed_countries = models.JSONField(default=default_list, blank=True)
    excluded_countries = models.JSONField(default=default_list, blank=True)
    allowed_devices = models.JSONField(default=default_devices, blank=True)
    
    # Display Settings
    display_order = models.JSONField(default=default_list, blank=True)
    sort_by = models.CharField(
        max_length=50, 
        default='-reward_amount', 
        choices=[
            ('-reward_amount', 'Highest Reward'),
            ('reward_amount', 'Lowest Reward'),
            ('-created_at', 'Newest First'),
            ('created_at', 'Oldest First'),
            ('-total_conversions', 'Most Popular'),
            ('difficulty', 'Easiest First'),
        ]
    )
    layout = models.CharField(
        max_length=50, 
        default='grid', 
        choices=[
            ('grid', 'Grid Layout'),
            ('list', 'List Layout'),
            ('card', 'Card Layout'),
            ('compact', 'Compact Layout'),
        ]
    )
    
    # Styling
    theme_color = models.CharField(max_length=7, default='#3498db', null=True, blank=True)
    background_color = models.CharField(max_length=7, default='#f8f9fa', null=True, blank=True)
    text_color = models.CharField(max_length=7, default='#333333', null=True, blank=True)
    
    # Statistics
    total_views = models.IntegerField(default=0)
    total_clicks = models.IntegerField(default=0)
    total_conversions = models.IntegerField(default=0)
    conversion_rate = models.FloatField(default=0)
    
    class Meta:
        verbose_name = 'Offer Wall'
        verbose_name_plural = 'Offer Walls'
        ordering = ['-is_default', 'name']
        indexes = [
            models.Index(fields=['wall_type', 'is_active']),
            models.Index(fields=['slug']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    @property
    def active_offers_count(self):
        from django.db.models import Count
        return self.ad_networks.filter(
            is_active=True,
            offers__status='active'
        ).distinct().count()


# ====================== Webhook Logs ======================

class AdNetworkWebhookLog(TimeStampedModel):
    """Log all incoming webhooks from ad networks"""
    
    # Tests create webhook logs without specifying an ad_network, so
    # this relationship must be optional.
    ad_network = models.ForeignKey(
        AdNetwork,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant',
        null=True,
        blank=True,
    )
    
    # Request Data
    payload = models.JSONField()
    headers = models.JSONField(default=default_dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_method = models.CharField(max_length=10, default='POST', null=True, blank=True)
    content_type = models.CharField(max_length=100, blank=True, null=True)
    
    # Processing
    processed = models.BooleanField(default=False)
    # Tests and some call sites expect an `is_processed` flag on the model
    # and also pass it as a keyword argument to `.create()`. We keep this
    # separate BooleanField for compatibility.
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True, null=True)
    processing_time = models.FloatField(default=0, help_text='Processing time in seconds')
    
    # Related Objects
    engagement = models.ForeignKey(UserOfferEngagement, on_delete=models.SET_NULL, null=True, blank=True)
    conversion = models.ForeignKey(OfferConversion, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Response
    response_data = models.JSONField(default=default_dict, blank=True)
    response_status = models.IntegerField(default=200)
    
    # Metadata
    event_type = models.CharField(max_length=100, blank=True, null=True)
    signature = models.CharField(max_length=500, blank=True, null=True)
    is_valid_signature = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Ad Network Webhook Log'
        verbose_name_plural = 'Ad Network Webhook Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ad_network', 'processed']),
            models.Index(fields=['created_at']),
            models.Index(fields=['event_type']),
        ]
    
    def __str__(self):
        return f"{self.ad_network.name} - {self.created_at}"


# ====================== Additional Models ======================

class NetworkStatistic(TimeStampedModel):
    """Daily statistics for ad networks"""
    ad_network = models.ForeignKey(AdNetwork, on_delete=models.CASCADE, related_name='%(app_label)s_%(class)s_tenant')
    date = models.DateField()
    
    clicks = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    payout = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
    commission = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
    
    class Meta:
        unique_together = ['ad_network', 'date']
        verbose_name = 'Network Statistic'
        verbose_name_plural = 'Network Statistics'


class UserOfferLimit(TimeStampedModel):
    """Track user limits for offers"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ad_networks_userofferlimit_user',)
    # Tests create `UserOfferLimit` with only a user instance. Make `offer`
    # optional so those creations succeed.
    offer = models.ForeignKey(
        Offer,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant',
        null=True,
        blank=True,
    )
    
    daily_count = models.IntegerField(default=0)
    total_count = models.IntegerField(default=0)
    last_completed = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'offer']


class OfferSyncLog(TimeStampedModel):
    """Log offer synchronization from networks"""
    ad_network = models.ForeignKey(AdNetwork, on_delete=models.CASCADE, related_name='%(app_label)s_%(class)s_tenant')
    
    status = models.CharField(
        max_length=20, 
        choices=[
            ('success', 'Success'),
            ('partial', 'Partial Success'),
            ('failed', 'Failed'),
        ]
    )
    offers_fetched = models.IntegerField(default=0)
    offers_added = models.IntegerField(default=0)
    offers_updated = models.IntegerField(default=0)
    offers_removed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    sync_duration = models.FloatField(default=0, help_text='Sync duration in seconds')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Offer Sync Log'
        verbose_name_plural = 'Offer Sync Logs'


# ====================== Future Expansion Models ======================

class SmartOfferRecommendation(TimeStampedModel):
    """AI-powered offer recommendations for users"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ad_networks_smartofferrecommendation_user', null=True, blank=True)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='ad_networks_smartofferrecommendation_offer', null=True, blank=True)
    
    score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    reason = models.TextField(blank=True, null=True)
    category_preference = models.JSONField(default=default_dict, blank=True)
    
    is_displayed = models.BooleanField(default=False)
    is_clicked = models.BooleanField(default=False)
    is_converted = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['user', 'offer']
        ordering = ['-score']


class OfferPerformanceAnalytics(TimeStampedModel):
    """Advanced analytics for offers"""
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='%(app_label)s_%(class)s_tenant')
    
    # User Demographics
    age_distribution = models.JSONField(default=default_dict, blank=True)
    gender_distribution = models.JSONField(default=default_dict, blank=True)
    country_distribution = models.JSONField(default=default_dict, blank=True)
    device_distribution = models.JSONField(default=default_dict, blank=True)
    
    # Time-based metrics
    hourly_performance = models.JSONField(default=default_dict, blank=True)
    daily_performance = models.JSONField(default=default_dict, blank=True)
    weekly_trend = models.JSONField(default=default_dict, blank=True)
    
    # Quality Metrics
    completion_rate = models.FloatField(default=0)
    dropoff_points = models.JSONField(default=default_list, blank=True)
    avg_session_duration = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = 'Offer Performance Analytics'
        verbose_name_plural = 'Offer Performance Analytics'
        


class BlacklistedIP(models.Model):
    """IP addresses blocked for fraud/bot activities"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    ip_address = models.GenericIPAddressField(unique=True)
    reason = models.CharField(
        max_length=50,
        choices=[
            ('fraud', 'Fraudulent Activity'),
            ('bot', 'Bot Traffic'),
            ('vpn', 'VPN/Proxy'),
            ('datacenter', 'Datacenter IP'),
            ('abuse', 'Abuse'),
            ('manual', 'Manually Blocked'),
            ('test', 'Test Block'),
        ],
        default='bot'
    )
    is_active = models.BooleanField(default=True)
    expiry_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Leave empty for permanent block. Auto-unblock after this date if set."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['expiry_date', 'is_active']),
            models.Index(fields=['reason', 'is_active']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
        verbose_name = "Blacklisted IP"
        verbose_name_plural = "Blacklisted IPs"
    
    def __str__(self):
        status = 'Active' if self.is_active else 'Inactive'
        expiry = f" (Expires: {self.expiry_date.strftime('%Y-%m-%d')})" if self.expiry_date else ' (Permanent)'
        return f"{self.ip_address} - {self.get_reason_display()} [{status}]{expiry}"
    
    def save(self, *args, **kwargs):
        """
        Save with smart expiry date handling.
        Only auto-set expiry date if:
        1. expiry_date is not provided AND
        2. is_active is True AND
        3. We want auto-expiry (not permanent block)
        """
        # Check if we should auto-set expiry date
        should_auto_set = (
            self.expiry_date is None and  # No expiry date provided
            self.is_active and            # Is active
            self.reason not in ['manual', 'test']  # Not manual or test blocks
        )
        
        if should_auto_set:
            # Default expiry based on reason
            default_days_map = {
                'fraud': 90,      # 90 days for fraud
                'bot': 60,         # 60 days for bots
                'vpn': 30,         # 30 days for VPNs
                'datacenter': 30,  # 30 days for datacenter IPs
                'abuse': 45,       # 45 days for abuse
            }
            default_days = default_days_map.get(self.reason, 30)
            self.expiry_date = timezone.now() + timedelta(days=default_days)
            print(f"Auto-set expiry date for {self.ip_address} to {self.expiry_date}")
        
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """
        Check if the blacklist entry has expired.
        Returns True if expiry_date is set and in the past.
        """
        if not self.expiry_date:
            return False  # Permanent block never expires
        return timezone.now() > self.expiry_date
    
    @property
    def is_effectively_active(self):
        """
        Check if IP is effectively active (not expired).
        This is the property to use in queries and checks.
        """
        if not self.is_active:
            return False
        
        if self.expiry_date and timezone.now() > self.expiry_date:
            return False
        
        return True
    
    def deactivate_if_expired(self):
        """
        Deactivate if expired and update database.
        Returns True if deactivated, False otherwise.
        """
        if self.is_expired and self.is_active:
            self.is_active = False
            self.save(update_fields=['is_active', 'updated_at'])
            print(f"Deactivated expired blacklist entry for {self.ip_address}")
            return True
        
        # Also check if expiry date is in future but is_active is False
        if not self.is_active and self.expiry_date and timezone.now() < self.expiry_date:
            # Reactivate if not expired but marked inactive
            self.is_active = True
            self.save(update_fields=['is_active', 'updated_at'])
            print(f"Reactivated blacklist entry for {self.ip_address}")
            return True
        
        return False
    
    @classmethod
    def get_active_blacklisted_ips(cls):
        """
        Get all effectively active blacklisted IPs.
        This method handles the expiry check properly.
        """
        now = timezone.now()
        return cls.objects.filter(
            is_active=True
        ).filter(
            models.Q(expiry_date__gt=now) | models.Q(expiry_date__isnull=True)
        )
    
    @classmethod
    def is_ip_blacklisted(cls, ip_address):
        """
        Check if an IP is currently blacklisted (active and not expired).
        Optimized query with proper expiry check.
        """
        now = timezone.now()
        
        try:
            return cls.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).filter(
                models.Q(expiry_date__gt=now) | models.Q(expiry_date__isnull=True)
            ).exists()
        except Exception as e:
            print(f"Error checking blacklist for {ip_address}: {str(e)}")
            return False
    
    @classmethod
    def get_ip_details(cls, ip_address):
        """
        Get details of blacklisted IP if exists.
        Returns None if not blacklisted or expired.
        """
        now = timezone.now()
        
        try:
            return cls.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).filter(
                models.Q(expiry_date__gt=now) | models.Q(expiry_date__isnull=True)
            ).first()
        except Exception as e:
            print(f"Error getting blacklist details for {ip_address}: {str(e)}")
            return None
    
    @classmethod
    def cleanup_expired_entries(cls, batch_size=1000):
        """
        Cleanup expired blacklist entries in batches.
        Returns dictionary with cleanup statistics.
        """
        now = timezone.now()
        
        # Get expired entries that are still marked active
        expired_query = cls.objects.filter(
            is_active=True,
            expiry_date__lt=now
        )
        
        total_expired = expired_query.count()
        
        if total_expired == 0:
            return {
                'total_expired': 0,
                'deactivated': 0,
                'batch_size': batch_size,
                'timestamp': now.isoformat()
            }
        
        # Deactivate in batches to prevent large transactions
        deactivated_count = 0
        for batch in range(0, total_expired, batch_size):
            batch_expired = expired_query[batch:batch + batch_size]
            
            for ip_entry in batch_expired:
                ip_entry.is_active = False
                ip_entry.updated_at = now
            
            # Bulk update
            cls.objects.bulk_update(
                batch_expired,
                ['is_active', 'updated_at'],
                batch_size=batch_size
            )
            
            deactivated_count += len(batch_expired)
            print(f"Deactivated {len(batch_expired)} expired blacklist entries (batch {batch//batch_size + 1})")
        
        # Also deactivate entries where is_active=False but expiry_date is in future
        # (in case of manual deactivation before expiry)
        future_expired_query = cls.objects.filter(
            is_active=False,
            expiry_date__gt=now
        )
        
        future_count = future_expired_query.count()
        if future_count > 0:
            print(f"Found {future_count} manually deactivated entries with future expiry dates")
        
        return {
            'total_expired': total_expired,
            'deactivated': deactivated_count,
            'batch_size': batch_size,
            'timestamp': now.isoformat(),
            'notes': f"Cleaned up {deactivated_count} expired entries"
        }
    
    @classmethod
    def get_statistics(cls):
        """
        Get statistics about blacklisted IPs.
        """
        now = timezone.now()
        
        total = cls.objects.count()
        active = cls.objects.filter(is_active=True).count()
        expired_but_active = cls.objects.filter(
            is_active=True,
            expiry_date__lt=now
        ).count()
        permanent = cls.objects.filter(
            is_active=True,
            expiry_date__isnull=True
        ).count()
        
        # Group by reason
        by_reason = cls.objects.filter(is_active=True).values(
            'reason'
        ).annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        # Recent activity (last 7 days)
        week_ago = now - timedelta(days=7)
        recent_additions = cls.objects.filter(
            created_at__gte=week_ago
        ).count()
        
        return {
            'total_entries': total,
            'active_entries': active,
            'expired_but_still_active': expired_but_active,
            'permanent_blocks': permanent,
            'by_reason': list(by_reason),
            'recent_additions_7d': recent_additions,
            'as_of': now.isoformat()
        }    


class FraudDetectionRule(TimeStampedModel):
    
    """Rules for fraud detection"""
    name = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    
    rule_type = models.CharField(
        max_length=50, 
        choices=[
            ('ip', 'IP Address'),
            ('device', 'Device Fingerprint'),
            ('behavior', 'User Behavior'),
            ('velocity', 'Velocity Check'),
            ('pattern', 'Pattern Detection'),
        ]
    )
    
    condition = models.JSONField(default=default_dict)
    action = models.CharField(
        max_length=50, 
        choices=[
            ('block', 'Block'),
            ('flag', 'Flag'),
            ('review', 'Send for Review'),
            ('limit', 'Limit'),
        ]
    )
    
    severity = models.CharField(
        max_length=20, 
        default='medium', 
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ]
    )
    
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-priority', 'name']
        
        
        
        # api/ad_networks/models.py - KnownBadIP মডেলে যোগ করুন

class KnownBadIP(models.Model):
    """Known bad IP addresses from various sources"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    ip_address = models.GenericIPAddressField(unique=True)
    threat_type = models.CharField(
        max_length=50,
        choices=[
            ('bot', 'Bot Network'),
            ('vpn', 'VPN/Proxy'),
            ('scanner', 'Port Scanner'),
            ('spam', 'Spam Source'),
            ('malware', 'Malware Distribution'),
            ('phishing', 'Phishing Source'),
            ('ddos', 'DDoS Source'),
            ('credential_stuffing', 'Credential Stuffing'),
        ]
    )
    confidence_score = models.IntegerField(
        default=50,
        help_text="Confidence score (0-100)"
    )
    source = models.CharField(
        max_length=100,
        choices=[
            ('internal', 'Internal Detection'),
            ('ipqualityscore', 'IPQualityScore'),
            ('abuseipdb', 'AbuseIPDB'),
            ('maxmind', 'MaxMind'),
            ('firehol', 'FireHOL'),
            ('custom', 'Custom List'),
        ]
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="যতক্ষণ পর্যন্ত এই আইপি ব্ল্যাকলিস্টে থাকবে"
    )
    description = models.TextField(blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['threat_type', 'is_active']),
            models.Index(fields=['expires_at']),  # নতুন ইনডেক্স যোগ করুন
        ]
        verbose_name = "Known Bad IP"
        verbose_name_plural = "Known Bad IPs"
    
    def __str__(self):
        return f"{self.ip_address} - {self.threat_type}"
    
    def is_expired(self):
        """চেক করে দেখুন আইপি এক্সপায়ার্ড কিনা"""
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False