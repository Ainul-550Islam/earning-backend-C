from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.utils import timezone
from decimal import Decimal
import uuid
from django.conf import settings


class OfferProvider(models.Model):
    """External offer providers (Tapjoy, AdGem, etc.)"""
    PROVIDER_TYPES = (
        ('tapjoy', 'Tapjoy'),
        ('adgem', 'AdGem'),
        ('adgate', 'AdGate Media'),
        ('offerwall', 'OfferToro'),
        ('persona', 'Persona.ly'),
        ('cpx', 'CPX Research'),
        ('bitlabs', 'BitLabs'),
        ('pollfish', 'Pollfish'),
        ('custom', 'Custom Provider'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('testing', 'Testing'),
        ('suspended', 'Suspended'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    provider_type = models.CharField(max_length=50, choices=PROVIDER_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # API Configuration
    api_key = models.CharField(max_length=500, blank=True)
    api_secret = models.CharField(max_length=500, blank=True)
    app_id = models.CharField(max_length=200, blank=True)
    publisher_id = models.CharField(max_length=200, blank=True)
    
    # URLs
    api_base_url = models.URLField(blank=True)
    webhook_url = models.URLField(blank=True)
    postback_url = models.URLField(blank=True)
    
    # Security
    secret_key = models.CharField(max_length=500, blank=True, help_text='For webhook signature verification')
    ip_whitelist = models.JSONField(default=list, blank=True)
    
    # Revenue Settings
    revenue_share = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('70.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Percentage of revenue shared with users'
    )
    
    # Rate Limits
    rate_limit_per_minute = models.IntegerField(default=60)
    rate_limit_per_hour = models.IntegerField(default=3600)
    
    # Statistics
    total_offers = models.IntegerField(default=0)
    total_conversions = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Settings
    auto_sync = models.BooleanField(default=True)
    sync_interval_minutes = models.IntegerField(default=60)
    last_sync = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    config = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider_type', 'status']),
            models.Index(fields=['status']),
        ]
        verbose_name = 'Offer Provider'
        verbose_name_plural = 'Offer Providers'
    
    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"
    
    def is_active(self):
        return self.status == 'active'


class OfferCategory(models.Model):
    """Categories for offers"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Icon class name')
    color = models.CharField(max_length=7, default='#3B82F6', help_text='Hex color code')
    
    # Display
    display_order = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Statistics
    offer_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Offer Category'
        verbose_name_plural = 'Offer Categories'
    
    def __str__(self):
        return self.name


class Offer(models.Model):
    """Main offer model"""
    OFFER_TYPES = (
        ('app_install', 'App Install'),
        ('signup', 'Sign Up'),
        ('survey', 'Survey'),
        ('video', 'Watch Video'),
        ('game', 'Play Game'),
        ('trial', 'Free Trial'),
        ('purchase', 'Make Purchase'),
        ('subscription', 'Subscription'),
        ('quiz', 'Quiz'),
        ('download', 'Download'),
        ('cashback', 'Cashback'),
        ('other', 'Other'),
    )
    
    PLATFORMS = (
        ('all', 'All Platforms'),
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web'),
        ('mobile', 'Mobile (Android + iOS)'),
        ('desktop', 'Desktop'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('disabled', 'Disabled'),
    )
    
    DIFFICULTY_LEVELS = (
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Provider Info
    provider = models.ForeignKey(
        OfferProvider,
        on_delete=models.CASCADE,
        related_name='offers'
    )
    external_offer_id = models.CharField(max_length=200, db_index=True)
    
    # Basic Info
    title = models.CharField(max_length=300)
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)
    
    # Categorization
    category = models.ForeignKey(
        OfferCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='offers'
    )
    offer_type = models.CharField(max_length=50, choices=OFFER_TYPES)
    tags = models.JSONField(default=list, blank=True)
    
    # Platform & Location
    platform = models.CharField(max_length=20, choices=PLATFORMS, default='all')
    countries = models.JSONField(default=list, blank=True, help_text='ISO 2-letter country codes')
    excluded_countries = models.JSONField(default=list, blank=True)
    
    # Media
    image_url = models.URLField(blank=True, validators=[URLValidator()])
    thumbnail_url = models.URLField(blank=True)
    icon_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    
    # URLs
    click_url = models.URLField(max_length=2000)
    tracking_url = models.URLField(max_length=2000, blank=True)
    preview_url = models.URLField(blank=True)
    
    # Reward Info
    payout = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0.000001'))]
    )
    currency = models.CharField(max_length=3, default='USD')
    
    # User-facing reward (after revenue share)
    reward_amount = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    reward_currency = models.CharField(max_length=10, default='Points')
    
    # Bonus rewards
    bonus_amount = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    bonus_condition = models.TextField(blank=True, help_text='Condition for bonus reward')
    
    # Difficulty & Time
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS, default='medium')
    estimated_time_minutes = models.IntegerField(default=5, validators=[MinValueValidator(1)])
    
    # Requirements
    min_age = models.IntegerField(default=18, validators=[MinValueValidator(13)])
    requires_signup = models.BooleanField(default=False)
    requires_card = models.BooleanField(default=False)
    requires_purchase = models.BooleanField(default=False)
    
    # Instructions
    instructions = models.TextField(blank=True)
    steps = models.JSONField(default=list, blank=True)
    requirements_text = models.TextField(blank=True)
    
    # Limits
    daily_cap = models.IntegerField(default=0, help_text='0 = unlimited')
    total_cap = models.IntegerField(default=0, help_text='0 = unlimited')
    user_limit = models.IntegerField(default=1, help_text='Times each user can complete')
    
    # Status & Validity
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_featured = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)
    is_recommended = models.BooleanField(default=False)
    
    # Dates
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    view_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    conversion_count = models.IntegerField(default=0)
    completion_rate = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Revenue tracking
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_payout = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Quality Score (0-100)
    quality_score = models.FloatField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Conversion tracking
    conversion_flow = models.JSONField(default=dict, blank=True, help_text='Steps in conversion funnel')
    postback_data = models.JSONField(default=dict, blank=True)
    
    # Fraud prevention
    fraud_score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_high_risk = models.BooleanField(default=False)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    provider_data = models.JSONField(default=dict, blank=True, help_text='Raw data from provider')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-is_featured', '-quality_score', '-reward_amount']
        indexes = [
            models.Index(fields=['provider', 'external_offer_id']),
            models.Index(fields=['status', 'platform']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['offer_type', 'status']),
            models.Index(fields=['-reward_amount', 'status']),
            models.Index(fields=['is_featured', 'status']),
            models.Index(fields=['end_date']),
        ]
        unique_together = ['provider', 'external_offer_id']
        verbose_name = 'Offer'
        verbose_name_plural = 'Offers'
    
    def __str__(self):
        return f"{self.title} - {self.reward_amount} {self.reward_currency}"
    
    def is_active(self):
        """Check if offer is currently active"""
        if self.status != 'active':
            return False
        
        now = timezone.now()
        
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        return True
    
    def is_available_for_user(self, user):
        """Check if offer is available for specific user"""
        from api.fraud_detection.models import OfferCompletion
        
        if not self.is_active():
            return False
        
        # Check user limit
        if self.user_limit > 0:
            completion_count = OfferCompletion.objects.filter(
                user=user,
                offer=self,
                status__in=['completed', 'pending']
            ).count()
            
            if completion_count >= self.user_limit:
                return False
        
        # Check daily cap
        if self.daily_cap > 0:
            today_completions = OfferCompletion.objects.filter(
                offer=self,
                status='completed',
                completed_at__date=timezone.now().date()
            ).count()
            
            if today_completions >= self.daily_cap:
                return False
        
        # Check total cap
        if self.total_cap > 0:
            if self.conversion_count >= self.total_cap:
                return False
        
        return True
    
    def increment_view(self):
        """Increment view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def increment_click(self):
        """Increment click count"""
        self.click_count += 1
        self.save(update_fields=['click_count'])
    
    def increment_conversion(self):
        """Increment conversion count and update completion rate"""
        self.conversion_count += 1
        
        if self.click_count > 0:
            self.completion_rate = (self.conversion_count / self.click_count) * 100
        
        self.save(update_fields=['conversion_count', 'completion_rate'])
    
    def calculate_quality_score(self):
        """Calculate offer quality score based on multiple factors"""
        score = 50  # Base score
        
        # Completion rate (30 points max)
        if self.click_count > 10:
            score += min(30, self.completion_rate * 0.3)
        
        # User engagement (20 points max)
        if self.view_count > 0:
            ctr = (self.click_count / self.view_count) * 100
            score += min(20, ctr * 0.2)
        
        # Revenue performance (20 points max)
        if self.total_revenue > 0:
            score += min(20, (float(self.total_revenue) / 1000) * 20)
        
        # Recency (10 points max)
        days_old = (timezone.now() - self.created_at).days
        if days_old < 30:
            score += 10
        elif days_old < 90:
            score += 5
        
        # Fraud score penalty (-30 points max)
        score -= min(30, self.fraud_score * 0.3)
        
        self.quality_score = max(0, min(100, score))
        self.save(update_fields=['quality_score'])
        
        return self.quality_score


class OfferClick(models.Model):
    """Track offer clicks"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='clicks')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offer_clicks')
    
    # Click data
    click_id = models.CharField(max_length=255, unique=True, db_index=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    # Device info
    device_type = models.CharField(max_length=50, blank=True)
    device_model = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=50, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    
    # Location
    country = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Referrer
    referrer_url = models.URLField(blank=True, max_length=2000)
    
    # Tracking
    session_id = models.CharField(max_length=255, blank=True)
    tracking_params = models.JSONField(default=dict, blank=True)
    
    # Status
    is_converted = models.BooleanField(default=False)
    converted_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    clicked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-clicked_at']
        indexes = [
            models.Index(fields=['offer', 'user']),
            models.Index(fields=['click_id']),
            models.Index(fields=['user', '-clicked_at']),
            models.Index(fields=['is_converted']),
        ]
        verbose_name = 'Offer Click'
        verbose_name_plural = 'Offer Clicks'
    
    def __str__(self):
        return f"{self.user.username} clicked {self.offer.title}"


class OfferConversion(models.Model):
    """Track successful offer conversions"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('chargeback', 'Chargeback'),
        ('reversed', 'Reversed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='conversions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offer_conversions')
    click = models.ForeignKey(OfferClick, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversions')
    
    # Conversion data
    conversion_id = models.CharField(max_length=255, unique=True, db_index=True)
    external_WalletTransaction_id = models.CharField(max_length=255, blank=True, db_index=True)
    
    # Payout
    payout_amount = models.DecimalField(max_digits=12, decimal_places=6)
    payout_currency = models.CharField(max_length=3, default='USD')
    
    # User reward
    reward_amount = models.DecimalField(max_digits=12, decimal_places=6)
    reward_currency = models.CharField(max_length=10, default='Points')
    
    # Bonus
    bonus_amount = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='offerwall_verified_conversions'
    )
    
    # Transaction
    transaction = models.ForeignKey(
        'wallet.WalletTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='offer_conversions'
    )
    
    # Provider data
    provider_data = models.JSONField(default=dict, blank=True)
    postback_data = models.JSONField(default=dict, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Timestamps
    converted_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-converted_at']
        indexes = [
            models.Index(fields=['offer', 'user']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', '-converted_at']),
            models.Index(fields=['external_WalletTransaction_id']),
        ]
        verbose_name = 'Offer Conversion'
        verbose_name_plural = 'Offer Conversions'
    
    def __str__(self):
        return f"{self.user.username} - {self.offer.title} - {self.status}"
    
    def approve(self, approver=None):
        """Approve conversion and credit user"""
        if self.status == 'approved':
            return False
        
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.verified_by = approver
        self.is_verified = True
        self.verified_at = timezone.now()
        
        # Create wallet transaction
        try:
            from api.wallet.models import WalletTransaction
            
            total_reward = self.reward_amount + self.bonus_amount
            
            txn = WalletTransaction.objects.create(
                user=self.user,
                transaction_type='credit',
                amount=total_reward,
                currency=self.reward_currency,
                description=f'Offer completed: {self.offer.title}',
                status='completed',
                metadata={
                    'offer_id': str(self.offer.id),
                    'offer_title': self.offer.title,
                    'conversion_id': self.conversion_id,
                    'base_reward': float(self.reward_amount),
                    'bonus_reward': float(self.bonus_amount),
                }
            )
            self.transaction = txn
        except Exception:
            pass  # wallet transaction optional — conversion still approved
        
        self.save()
        
        return True
    
    def reject(self, reason='', rejector=None):
        """Reject conversion"""
        self.status = 'rejected'
        self.rejection_reason = reason
        self.verified_by = rejector
        self.verified_at = timezone.now()
        self.save()


class OfferWall(models.Model):
    """Custom offer wall configurations"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Display settings
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    banner_image = models.URLField(blank=True)
    
    # Filters
    categories = models.ManyToManyField(OfferCategory, blank=True, related_name='offer_walls')
    providers = models.ManyToManyField(OfferProvider, blank=True, related_name='offer_walls')
    offer_types = models.JSONField(default=list, blank=True)
    platforms = models.JSONField(default=list, blank=True)
    
    # Targeting
    countries = models.JSONField(default=list, blank=True)
    min_payout = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    
    # Display
    offers_per_page = models.IntegerField(default=20)
    sort_by = models.CharField(max_length=50, default='quality_score')
    is_active = models.BooleanField(default=True)
    
    # Settings
    config = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Offer Wall'
        verbose_name_plural = 'Offer Walls'
    
    def __str__(self):
        return self.name
    
    def get_offers(self, user=None):
        """Get filtered offers for this wall"""
        offers = Offer.objects.filter(status='active')
        
        if self.categories.exists():
            offers = offers.filter(category__in=self.categories.all())
        
        if self.providers.exists():
            offers = offers.filter(provider__in=self.providers.all())
        
        if self.offer_types:
            offers = offers.filter(offer_type__in=self.offer_types)
        
        if self.platforms:
            offers = offers.filter(platform__in=self.platforms)
        
        if self.min_payout > 0:
            offers = offers.filter(payout__gte=self.min_payout)
        
        return offers.order_by(f'-{self.sort_by}')