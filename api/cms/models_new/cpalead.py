from datetime import timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/models_new/cpalead.py
"""
CPAlead Core Integration Models — based on real CPAlead documentation.

CPAlead real features (2024/2025):
1. Offerwall — virtual currency (coins/points), customizable UI, postback
2. Content Locker — lock content behind offer completion (zero_hours mode)
3. Link Locker — lock URLs behind offer completion
4. File Locker — lock file downloads
5. Offer Feed API — JSON feed of offers by country/device
6. Postback — subid + lead_id + payout + password params
7. USDT payment (Jul 2025, $25 min), PayPal, Payoneer, Wire
8. Quiz/personality offers
9. Daily payouts ($1 minimum)

Postback URL format (official CPAlead docs):
    https://yoursite.com/api/cms/webhooks/cpalead/
        ?subid={subid}
        &payout={payout}
        &lead_id={lead_id}
        &password={password}
        &campaign_id={campaign_id}    (optional)
        &ip={ip}                       (optional)
        &device={device}               (optional)
"""
import uuid
import hashlib
import hmac
import logging
from decimal import Decimal
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.cache import cache
from django.core.validators import MinValueValidator, MaxValueValidator

logger = logging.getLogger(__name__)


def _default_dict():
    return {}


def _default_list():
    return []


# ─────────────────────────────────────────────────────────────────
# Virtual Currency System
# CPAlead supports custom coins/points with configurable ratio
# e.g. $1 = 100 coins, set ratio=100
# ─────────────────────────────────────────────────────────────────

class VirtualCurrency(models.Model):
    """
    Virtual currency config (coins, points, credits).
    CPAlead Offerwall uses this for reward display.
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(
        _("Currency Name"), max_length=50, default='Coins',
        help_text=_("e.g. Coins, Points, Credits, Gems")
    )
    symbol = models.CharField(_("Symbol"), max_length=20, default='🪙')
    # How many virtual units per $1 USD
    usd_ratio = models.DecimalField(
        _("USD to Virtual Ratio"), max_digits=10, decimal_places=2, default=100,
        help_text=_("e.g. 100 means $1 = 100 coins")
    )
    min_earn_per_offer = models.DecimalField(
        _("Min Earn Per Offer"), max_digits=10, decimal_places=2, default=10
    )
    max_earn_per_offer = models.DecimalField(
        _("Max Earn Per Offer"), max_digits=10, decimal_places=2, default=1000
    )
    daily_earn_cap = models.DecimalField(
        _("Daily Earn Cap (virtual units)"), max_digits=10, decimal_places=2, default=5000
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Virtual Currency")
        verbose_name_plural = _("Virtual Currencies")

    def __str__(self):
        return f"{self.name} (1 USD = {self.usd_ratio} {self.name})"

    def usd_to_virtual(self, usd_amount: Decimal) -> Decimal:
        """Convert USD payout to virtual currency units."""
        return (Decimal(str(usd_amount)) * self.usd_ratio).quantize(Decimal('1'))

    def virtual_to_usd(self, virtual_amount: Decimal) -> Decimal:
        """Convert virtual units back to USD."""
        if self.usd_ratio == 0:
            return Decimal('0')
        return (Decimal(str(virtual_amount)) / self.usd_ratio).quantize(Decimal('0.0001'))

    @classmethod
    def get_active(cls):
        cache_key = 'virtual_currency_active'
        vc = cache.get(cache_key)
        if vc is None:
            try:
                vc = cls.objects.filter(is_active=True).latest('created_at')
            except cls.DoesNotExist:
                vc = None
            cache.set(cache_key, vc, 3600)
        return vc


class UserVirtualBalance(models.Model):
    """Per-user virtual currency balance."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='virtual_balance', verbose_name=_("User")
    )
    currency = models.ForeignKey(
        VirtualCurrency, on_delete=models.PROTECT,
        related_name='user_balances', verbose_name=_("Currency")
    )
    balance = models.DecimalField(
        _("Balance"), max_digits=14, decimal_places=2, default=0
    )
    total_earned = models.DecimalField(
        _("Total Earned"), max_digits=14, decimal_places=2, default=0
    )
    total_spent = models.DecimalField(
        _("Total Spent"), max_digits=14, decimal_places=2, default=0
    )
    today_earned = models.DecimalField(
        _("Today Earned"), max_digits=14, decimal_places=2, default=0
    )
    last_earn_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("User Virtual Balance")
        verbose_name_plural = _("User Virtual Balances")

    def __str__(self):
        return f"{self.user.username}: {self.balance} {self.currency}"

    def add_coins(self, amount: Decimal, reason: str = '') -> bool:
        """Add virtual currency. Thread-safe."""
        try:
            from django.db import transaction
            with transaction.atomic():
                obj = UserVirtualBalance.objects.select_for_update().get(pk=self.pk)
                # Reset today_earned if it's a new day
                today = timezone.now().date()
                if obj.last_earn_date != today:
                    obj.today_earned = Decimal('0')
                    obj.last_earn_date = today
                # Check daily cap
                if obj.today_earned + amount > obj.currency.daily_earn_cap:
                    amount = obj.currency.daily_earn_cap - obj.today_earned
                    if amount <= 0:
                        return False
                obj.balance = F('balance') + amount
                obj.total_earned = F('total_earned') + amount
                obj.today_earned = F('today_earned') + amount
                obj.save()
            self.refresh_from_db()
            return True
        except Exception as e:
            logger.error(f"Error adding coins for user {self.user_id}: {e}")
            return False

    def spend_coins(self, amount: Decimal) -> bool:
        """Spend virtual currency. Returns False if insufficient balance."""
        try:
            from django.db import transaction
            with transaction.atomic():
                obj = UserVirtualBalance.objects.select_for_update().get(pk=self.pk)
                if obj.balance < amount:
                    return False
                obj.balance = F('balance') - amount
                obj.total_spent = F('total_spent') + amount
                obj.save()
            self.refresh_from_db()
            return True
        except Exception as e:
            logger.error(f"Error spending coins for user {self.user_id}: {e}")
            return False


class VirtualTransaction(models.Model):
    """Log of all virtual currency earn/spend events."""
    TX_TYPES = [
        ('earn_offer', _('Earned from Offer')),
        ('earn_banner', _('Earned from Banner')),
        ('earn_content', _('Earned from Content Read')),
        ('earn_referral', _('Earned from Referral')),
        ('earn_bonus', _('Bonus Reward')),
        ('earn_quiz', _('Earned from Quiz')),
        ('spend_withdrawal', _('Spent: Withdrawal')),
        ('spend_purchase', _('Spent: In-app Purchase')),
        ('admin_adjust', _('Admin Adjustment')),
        ('refund', _('Refund')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='virtual_transactions'
    )
    tx_type = models.CharField(
        _("Transaction Type"), max_length=30, choices=TX_TYPES, db_index=True
    )
    amount = models.DecimalField(
        _("Amount (virtual units)"), max_digits=14, decimal_places=2
    )
    balance_before = models.DecimalField(
        _("Balance Before"), max_digits=14, decimal_places=2, default=0
    )
    balance_after = models.DecimalField(
        _("Balance After"), max_digits=14, decimal_places=2, default=0
    )
    usd_equivalent = models.DecimalField(
        _("USD Equivalent"), max_digits=10, decimal_places=4, null=True, blank=True
    )
    description = models.CharField(_("Description"), max_length=500, blank=True)
    source_type = models.CharField(_("Source Type"), max_length=100, blank=True)
    source_id = models.CharField(_("Source ID"), max_length=200, blank=True)
    # CPAlead postback data
    cpalead_lead_id = models.CharField(_("CPAlead Lead ID"), max_length=200, blank=True)
    cpalead_campaign_id = models.CharField(_("CPAlead Campaign ID"), max_length=200, blank=True)
    metadata = models.JSONField(_("Metadata"), default=_default_dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Virtual Transaction")
        verbose_name_plural = _("Virtual Transactions")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'tx_type', 'created_at']),
            models.Index(fields=['uuid']),
            models.Index(fields=['cpalead_lead_id']),
        ]

    def __str__(self):
        return f"{self.user.username} {self.get_tx_type_display()} {self.amount}"


# ─────────────────────────────────────────────────────────────────
# Offerwall Configuration
# Based on real CPAlead dashboard options
# ─────────────────────────────────────────────────────────────────

class OfferWallConfig(models.Model):
    """
    CPAlead Offerwall configuration.
    From CPAlead docs: title, header, currency_name, currency_ratio, custom CSS/HTML.
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Config Name"), max_length=200, default='Main Offerwall')
    # CPAlead dashboard fields (exact match)
    offerwall_title = models.CharField(
        _("Offerwall Title"), max_length=200, default='Earn Coins',
        help_text=_("Title shown at top of offerwall")
    )
    header_title = models.CharField(
        _("Header Title"), max_length=200, blank=True,
        help_text=_("Your app/site name in the header")
    )
    currency = models.ForeignKey(
        VirtualCurrency, on_delete=models.SET_NULL, null=True,
        related_name='offerwalls', verbose_name=_("Virtual Currency")
    )
    # CPAlead publisher config
    publisher_id = models.CharField(_("Publisher ID"), max_length=100, blank=True)
    website_id = models.CharField(_("Website ID"), max_length=100, blank=True)
    # Display settings
    custom_css = models.TextField(_("Custom CSS"), blank=True)
    custom_html_header = models.TextField(_("Custom HTML Header"), blank=True)
    custom_html_footer = models.TextField(_("Custom HTML Footer"), blank=True)
    background_color = models.CharField(_("Background Color"), max_length=20, default='#ffffff')
    button_color = models.CharField(_("Button Color"), max_length=20, default='#007bff')
    text_color = models.CharField(_("Text Color"), max_length=20, default='#333333')
    # Targeting
    target_countries = models.JSONField(
        _("Target Countries"), default=_default_list,
        help_text=_("ISO country codes, empty=all")
    )
    target_devices = models.JSONField(
        _("Target Devices"), default=_default_list,
        help_text=_("desktop, mobile, tablet, empty=all")
    )
    # Behavior
    show_offer_types = models.JSONField(
        _("Offer Types to Show"), default=_default_list,
        help_text=_("cpa, cpi, survey, quiz, video — empty=all")
    )
    min_payout_usd = models.DecimalField(
        _("Min Payout (USD)"), max_digits=8, decimal_places=4, default=0
    )
    is_active = models.BooleanField(default=True)
    # Stats
    total_views = models.PositiveIntegerField(default=0)
    total_completions = models.PositiveIntegerField(default=0)
    total_payout_usd = models.DecimalField(
        _("Total Payout USD"), max_digits=14, decimal_places=2, default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Offerwall Config")
        verbose_name_plural = _("Offerwall Configs")

    def __str__(self):
        return self.name

    def generate_embed_code(self, user=None, user_ip='', device='desktop'):
        """
        Generate CPAlead offerwall embed code.
        Based on CPAlead's official embed script format.
        """
        sub_id = str(user.id) if user else 'anonymous'
        embed = f"""<!-- CPAlead Offerwall: {self.offerwall_title} -->
<div id="cpalead-offerwall-{self.pk}" class="cpalead-offerwall-container">
    <script>
        (function() {{
            var cpl = document.createElement('script');
            cpl.src = 'https://cdn.cpalead.com/offerwall/v2/offerwall.min.js';
            cpl.setAttribute('data-pub', '{self.publisher_id}');
            cpl.setAttribute('data-website', '{self.website_id}');
            cpl.setAttribute('data-subid', '{sub_id}');
            cpl.setAttribute('data-currency', '{self.currency if self.currency else "Coins"}');
            cpl.setAttribute('data-title', '{self.offerwall_title}');
            cpl.setAttribute('data-color', '{self.button_color}');
            cpl.setAttribute('data-bgcolor', '{self.background_color}');
            document.currentScript.parentNode.insertBefore(cpl, document.currentScript);
        }})();
    </script>
</div>
{('<style>' + self.custom_css + '</style>') if self.custom_css else ''}"""
        return embed

    def get_offer_feed_url(self, user_ip='', device='desktop', limit=20):
        """
        Get CPAlead offer feed URL.
        Real API: https://api.cpalead.com/offers.php?pub={pub}&user_ip={ip}&device={device}
        """
        base_url = "https://api.cpalead.com/offers.php"
        params = [
            f"pub={self.publisher_id}",
            f"user_ip={user_ip}",
            f"device={device}",
            f"limit={limit}",
        ]
        if self.target_countries:
            params.append(f"country={'|'.join(self.target_countries)}")
        return f"{base_url}?{'&'.join(params)}"


# ─────────────────────────────────────────────────────────────────
# Content Locker
# CPAlead's core feature: lock content behind offer completion
# ─────────────────────────────────────────────────────────────────

class ContentLocker(models.Model):
    """
    CPAlead Content Locker — lock any content behind offer completion.

    Zero Hours Mode (from CPAlead docs): require offer completion
    every time the user accesses the content. Ideal for reward-based systems.

    Types:
    - content: Lock HTML/text content
    - link: Lock a URL (Link Locker)
    - file: Lock a file download (File Locker)
    - page: Lock an entire CMS page
    - blog: Lock a blog post
    """
    LOCKER_TYPES = [
        ('content', _('Content Block')),
        ('link', _('Link Locker')),
        ('file', _('File Locker')),
        ('page', _('CMS Page')),
        ('blog', _('Blog Post')),
        ('video', _('Video')),
        ('download', _('Download')),
    ]

    UNLOCK_MODES = [
        ('session', _('Once per session')),
        ('24h', _('Once per 24 hours')),
        ('7d', _('Once per 7 days')),
        ('permanent', _('Unlock permanently')),
        ('zero_hours', _('Every time (Zero Hours)')),  # CPAlead term
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Locker Name"), max_length=200)
    locker_type = models.CharField(
        _("Locker Type"), max_length=20, choices=LOCKER_TYPES, default='content', db_index=True
    )
    offerwall = models.ForeignKey(
        OfferWallConfig, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lockers', verbose_name=_("Offerwall Config")
    )
    # Locker display
    title = models.CharField(
        _("Locker Title"), max_length=300,
        default='Please complete an action below to unlock:'
    )
    description = models.TextField(_("Description"), blank=True)
    locked_content = models.TextField(
        _("Locked Content/URL/Path"), blank=True,
        help_text=_("The actual content, URL, or file path to unlock")
    )
    # Preview shown while locked
    preview_content = models.TextField(
        _("Preview/Teaser Content"), blank=True,
        help_text=_("Blurred or partial content shown before unlock")
    )
    # Unlock behavior
    unlock_mode = models.CharField(
        _("Unlock Mode"), max_length=20, choices=UNLOCK_MODES, default='24h'
    )
    # Zero hours = require completion every visit (CPAlead official term)
    zero_hours_mode = models.BooleanField(
        _("Zero Hours Mode"), default=False,
        help_text=_("CPAlead: Require offer completion every access")
    )
    # 🆕 Zero-hours mode specific settings
    session_timeout_minutes = models.PositiveIntegerField(
        _("Session Timeout (minutes)"), default=30,
        help_text=_("Session duration for zero-hours mode access")
    )
    require_unique_offers = models.BooleanField(
        _("Require Unique Offers"), default=True,
        help_text=_("Require different offers for each zero-hours unlock")
    )
    max_daily_unlocks = models.PositiveIntegerField(
        _("Max Daily Unlocks"), default=10,
        help_text=_("Maximum unlocks per day in zero-hours mode")
    )
    zero_hours_multiplier = models.DecimalField(
        _("Zero-Hours Reward Multiplier"), max_digits=5, decimal_places=2, 
        default=Decimal('1.0'),
        help_text=_("Reward multiplier for zero-hours mode completions")
    )
    # Display customization
    custom_css = models.TextField(_("Custom CSS"), blank=True)
    background_color = models.CharField(max_length=20, default='#f8f9fa', blank=True)
    overlay_opacity = models.FloatField(
        _("Overlay Opacity"), default=0.9,
        validators=[MinValueValidator(0.1), MaxValueValidator(1.0)]
    )
    blur_preview = models.BooleanField(
        _("Blur Preview"), default=True,
        help_text=_("Blur the preview content while locked")
    )
    blur_amount = models.IntegerField(_("Blur Amount (px)"), default=8)
    # Related CMS object
    related_page_slug = models.SlugField(_("Related Page Slug"), blank=True)
    related_blog_slug = models.SlugField(_("Related Blog Slug"), blank=True)
    # Reward when unlocked
    reward_user_on_unlock = models.BooleanField(
        _("Reward User on Unlock"), default=True
    )
    reward_virtual_amount = models.DecimalField(
        _("Virtual Reward Amount"), max_digits=10, decimal_places=2, default=0
    )
    is_active = models.BooleanField(default=True)
    # Stats
    total_views = models.PositiveIntegerField(default=0)
    total_unlocks = models.PositiveIntegerField(default=0)
    conversion_rate = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Content Locker")
        verbose_name_plural = _("Content Lockers")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['locker_type', 'is_active']),
            models.Index(fields=['uuid']),
            models.Index(fields=['related_page_slug']),
            models.Index(fields=['related_blog_slug']),
            # 🆕 Zero-hours mode indexes
            models.Index(fields=['zero_hours_mode', 'is_active']),
            models.Index(fields=['id', 'zero_hours_mode']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_locker_type_display()})"

    def is_locked_for_user(self, user=None, session_key='') -> dict:
        """
        Enhanced lock checking for zero-hours mode.
        
        Returns: {
            'is_locked': bool,
            'requires_session': bool,
            'session_id': str|None,
            'reason': str,
            'daily_unlocks_remaining': int,
            'session_expires_at': datetime|None
        }
        """
        if not self.is_active:
            return {'is_locked': False, 'requires_session': False, 'session_id': None, 
                    'reason': 'inactive', 'daily_unlocks_remaining': 0, 'session_expires_at': None}
        
        # Zero-hours mode requires session management
        if self.zero_hours_mode:
            return self._check_zero_hours_lock(user, session_key)
        
        # Standard unlock mode checking
        if user and user.is_authenticated:
            unlock = LockerUnlock.objects.filter(
                locker=self, user=user, is_valid=True
            ).first()
            if unlock and not unlock.is_expired():
                return {'is_locked': False, 'requires_session': False, 'session_id': None,
                        'reason': 'unlocked', 'daily_unlocks_remaining': 0, 'session_expires_at': unlock.expires_at}
        
        elif session_key:
            unlock = LockerUnlock.objects.filter(
                locker=self, session_key=session_key, is_valid=True
            ).first()
            if unlock and not unlock.is_expired():
                return {'is_locked': False, 'requires_session': False, 'session_id': None,
                        'reason': 'unlocked', 'daily_unlocks_remaining': 0, 'session_expires_at': unlock.expires_at}
        
        return {'is_locked': True, 'requires_session': False, 'session_id': None,
                'reason': 'not_unlocked', 'daily_unlocks_remaining': 0, 'session_expires_at': None}
    
    def _check_zero_hours_lock(self, user=None, session_key='') -> dict:
        """
        Check lock status specifically for zero-hours mode.
        """
        from ..services_new.ZeroHoursSession import ZeroHoursSession
        
        # Check daily unlock limit
        if user and user.is_authenticated:
            today_unlocks = ZeroHoursSession.get_daily_unlock_count(user.id, self.id)
            remaining = max(0, self.max_daily_unlocks - today_unlocks)
            
            if remaining <= 0:
                return {'is_locked': True, 'requires_session': False, 'session_id': None,
                        'reason': 'daily_limit_reached', 'daily_unlocks_remaining': 0, 
                        'session_expires_at': None}
        
        # Check for existing active session
        session_id = ZeroHoursSession.get_active_session(user.id if user else session_key, self.id)
        
        if session_id:
            session = ZeroHoursSession.get_session(session_id)
            if session and session.get('status') == 'active':
                return {'is_locked': False, 'requires_session': False, 'session_id': session_id,
                        'reason': 'session_active', 'daily_unlocks_remaining': remaining if user else 0,
                        'session_expires_at': session.get('expires_at')}
        
        return {'is_locked': True, 'requires_session': True, 'session_id': None,
                'reason': 'zero_hours_requires_session', 'daily_unlocks_remaining': remaining if user else 0,
                'session_expires_at': None}

    def record_view(self):
        ContentLocker.objects.filter(pk=self.pk).update(total_views=F('total_views') + 1)

    def record_unlock(self):
        ContentLocker.objects.filter(pk=self.pk).update(
            total_unlocks=F('total_unlocks') + 1
        )
        self.refresh_from_db()
        if self.total_views > 0:
            rate = (self.total_unlocks / self.total_views) * 100
            ContentLocker.objects.filter(pk=self.pk).update(conversion_rate=rate)


class LockerUnlock(models.Model):
    """Track when users have unlocked a ContentLocker."""
    UNLOCK_SOURCE = [
        ('cpalead_offer', _('CPAlead Offer')),
        ('cpalead_postback', _('CPAlead Postback')),
        ('manual', _('Manual/Admin')),
        ('reward', _('Reward Coins')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    locker = models.ForeignKey(
        ContentLocker, on_delete=models.CASCADE, related_name='unlocks'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='locker_unlocks'
    )
    session_key = models.CharField(max_length=100, blank=True)
    unlock_source = models.CharField(
        max_length=30, choices=UNLOCK_SOURCE, default='cpalead_offer'
    )
    unlocked_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_valid = models.BooleanField(default=True)
    # CPAlead conversion data
    cpalead_lead_id = models.CharField(max_length=200, blank=True)
    payout_usd = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Locker Unlock")
        verbose_name_plural = _("Locker Unlocks")
        ordering = ['-unlocked_at']
        indexes = [
            models.Index(fields=['locker', 'user', 'is_valid']),
            models.Index(fields=['session_key', 'locker']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.locker.name} unlocked by {self.user or self.session_key}"

    def is_expired(self) -> bool:
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False


# ─────────────────────────────────────────────────────────────────
# Click Log — Track all CPAlead clicks with click_id
# ─────────────────────────────────────────────────────────────────

class ClickLog(models.Model):
    """
    Track every CPAlead offer/banner click.
    click_id is used for postback deduplication (lead_id dedup).
    """
    CLICK_SOURCES = [
        ('offerwall', _('Offerwall')),
        ('banner', _('Banner')),
        ('content_locker', _('Content Locker')),
        ('link_locker', _('Link Locker')),
        ('file_locker', _('File Locker')),
        ('direct', _('Direct Link')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # CPAlead tracking params
    click_id = models.CharField(
        _("Click ID (subid)"), max_length=200, db_index=True,
        help_text=_("Passed as subid to CPAlead, returned in postback")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cpalead_clicks'
    )
    session_key = models.CharField(max_length=100, blank=True)
    offer_id = models.CharField(_("Offer ID"), max_length=200, blank=True)
    campaign_id = models.CharField(_("Campaign ID"), max_length=200, blank=True)
    click_source = models.CharField(
        _("Click Source"), max_length=30, choices=CLICK_SOURCES, default='offerwall'
    )
    # Request data
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(
        max_length=20,
        choices=[('desktop', 'Desktop'), ('mobile', 'Mobile'), ('tablet', 'Tablet')],
        default='desktop'
    )
    country_code = models.CharField(max_length=5, blank=True)
    # State
    has_converted = models.BooleanField(_("Converted"), default=False, db_index=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    payout_usd = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    is_fraud = models.BooleanField(_("Flagged as Fraud"), default=False)
    fraud_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Click Log")
        verbose_name_plural = _("Click Logs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['click_id']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['has_converted', 'created_at']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        status = "✓" if self.has_converted else "○"
        return f"{status} Click {self.click_id} by {self.user or self.ip_address}"

    @classmethod
    def create_click(cls, user=None, session_key='', offer_id='', campaign_id='',
                     click_source='offerwall', ip='', user_agent='',
                     device_type='desktop', country_code=''):
        """Create a click log entry and return the click_id (subid)."""
        import time, hashlib
        # Generate unique click_id to use as CPAlead subid
        raw = f"{user.id if user else session_key}_{offer_id}_{time.time()}"
        click_id = hashlib.md5(raw.encode()).hexdigest()[:20]
        return cls.objects.create(
            click_id=click_id,
            user=user,
            session_key=session_key,
            offer_id=offer_id,
            campaign_id=campaign_id,
            click_source=click_source,
            ip_address=ip or None,
            user_agent=user_agent,
            device_type=device_type,
            country_code=country_code,
        )

    def mark_converted(self, payout_usd):
        """Mark click as converted when postback is received."""
        self.has_converted = True
        self.converted_at = timezone.now()
        self.payout_usd = payout_usd
        self.save(update_fields=['has_converted', 'converted_at', 'payout_usd'])


# ─────────────────────────────────────────────────────────────────
# Conversion Log — Record of all CPAlead postback conversions
# ─────────────────────────────────────────────────────────────────

class ConversionLog(models.Model):
    """
    Authoritative record of every CPAlead postback conversion.

    CPAlead postback params (official docs):
    - subid: your user reference (user_id you passed)
    - payout: reward amount in USD
    - lead_id: CPAlead's unique conversion ID (use for deduplication)
    - password: your postback secret for validation
    - campaign_id: offer campaign (optional)
    - ip: user IP (optional)
    """
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('approved', _('Approved — Reward Paid')),
        ('rejected', _('Rejected')),
        ('fraud', _('Rejected — Fraud')),
        ('cap_exceeded', _('Rejected — Daily Cap')),
        ('duplicate', _('Rejected — Duplicate')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # CPAlead official postback parameters
    subid = models.CharField(
        _("SubID (user ref)"), max_length=200, db_index=True,
        help_text=_("Your user_id passed to CPAlead as {subid}")
    )
    lead_id = models.CharField(
        _("Lead ID"), max_length=200, unique=True, db_index=True,
        help_text=_("CPAlead's unique conversion ID — used for dedup")
    )
    payout_usd = models.DecimalField(
        _("Payout USD"), max_digits=10, decimal_places=4,
        help_text=_("{payout} from CPAlead postback")
    )
    campaign_id = models.CharField(
        _("Campaign ID"), max_length=200, blank=True,
        help_text=_("{campaign_id} from CPAlead postback")
    )
    # Resolved user
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cpalead_conversions'
    )
    # Reward awarded
    virtual_amount_awarded = models.DecimalField(
        _("Virtual Currency Awarded"), max_digits=14, decimal_places=2, default=0
    )
    usd_amount_awarded = models.DecimalField(
        _("USD Awarded"), max_digits=10, decimal_places=4, default=0
    )
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    rejection_reason = models.CharField(max_length=200, blank=True)
    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    raw_postback_data = models.JSONField(
        _("Raw Postback Data"), default=_default_dict,
        help_text=_("Full postback request params for debugging")
    )
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Conversion Log")
        verbose_name_plural = _("Conversion Logs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subid', 'created_at']),
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['lead_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"[{self.status}] lead_id={self.lead_id} ${self.payout_usd} → {self.user}"

    def approve(self, virtual_amount, usd_amount):
        """Mark conversion as approved."""
        self.status = 'approved'
        self.virtual_amount_awarded = virtual_amount
        self.usd_amount_awarded = usd_amount
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'virtual_amount_awarded', 'usd_amount_awarded', 'processed_at'])

    def reject(self, reason: str):
        """Mark conversion as rejected."""
        status_map = {
            'duplicate': 'duplicate',
            'fraud': 'fraud',
            'cap_exceeded': 'cap_exceeded',
        }
        self.status = status_map.get(reason, 'rejected')
        self.rejection_reason = reason
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'rejection_reason', 'processed_at'])

    @classmethod
    def is_duplicate(cls, lead_id: str) -> bool:
        """Check if this lead_id has already been processed."""
        return cls.objects.filter(lead_id=lead_id).exclude(status='pending').exists()


# ─────────────────────────────────────────────────────────────────
# Zero Hours Session Log — Track zero-hours mode sessions
# ─────────────────────────────────────────────────────────────────

class ZeroHoursSessionLog(models.Model):
    """
    Track all zero-hours mode sessions for analytics and reporting.
    
    This model provides comprehensive analytics for zero-hours mode performance,
    user behavior, and revenue tracking.
    """
    SESSION_STATUS = [
        ('active', _('Active')),
        ('completed', _('Completed')),
        ('expired', _('Expired')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    session_id = models.CharField(
        _("Session ID"), max_length=100, db_index=True,
        help_text=_("Zero-hours session identifier")
    )
    locker = models.ForeignKey(
        ContentLocker, on_delete=models.CASCADE,
        related_name='zero_hours_logs', verbose_name=_("Content Locker")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='zero_hours_sessions'
    )
    session_key = models.CharField(
        _("Session Key"), max_length=100, blank=True,
        help_text=_("Anonymous session identifier")
    )
    
    # Timing
    started_at = models.DateTimeField(_("Started At"))
    completed_at = models.DateTimeField(
        _("Completed At"), null=True, blank=True
    )
    duration_seconds = models.PositiveIntegerField(
        _("Duration (seconds)"), null=True, blank=True,
        help_text=_("Time from start to completion/expiry")
    )
    
    # Offer tracking
    offers_required = models.PositiveIntegerField(
        _("Offers Required"), default=1
    )
    offers_completed = models.JSONField(
        _("Completed Offers"), default=list,
        help_text=_("List of completed offer IDs/lead_ids")
    )
    
    # Financial tracking
    total_payout_usd = models.DecimalField(
        _("Total Payout USD"), max_digits=10, decimal_places=4, default=0,
        help_text=_("Total USD earned from this session")
    )
    virtual_currency_awarded = models.DecimalField(
        _("Virtual Currency Awarded"), max_digits=14, decimal_places=2, default=0,
        help_text=_("Virtual currency units awarded to user")
    )
    
    # Status and metadata
    status = models.CharField(
        _("Status"), max_length=20, choices=SESSION_STATUS, default='active',
        db_index=True
    )
    ip_address = models.GenericIPAddressField(
        _("IP Address"), null=True, blank=True
    )
    user_agent = models.TextField(_("User Agent"), blank=True)
    country_code = models.CharField(_("Country Code"), max_length=5, blank=True)
    
    # Additional analytics data
    metadata = models.JSONField(
        _("Metadata"), default=_default_dict, blank=True,
        help_text=_("Additional session data and configuration")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Zero Hours Session Log")
        verbose_name_plural = _("Zero Hours Session Logs")
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['locker', 'status', 'started_at']),
            models.Index(fields=['user', 'status', 'started_at']),
            models.Index(fields=['status', 'started_at']),
            models.Index(fields=['completed_at']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        user_info = f"user {self.user.id}" if self.user else f"session {self.session_key}"
        return f"[{self.status}] {self.locker.name} → {user_info} (${self.total_payout_usd})"
    
    def save(self, *args, **kwargs):
        # Calculate duration if completed
        if self.completed_at and self.started_at:
            self.duration_seconds = int((self.completed_at - self.started_at).total_seconds())
        super().save(*args, **kwargs)
    
    def mark_completed(self, payout_usd: Decimal, virtual_amount: Decimal = None):
        """Mark session as completed with payout."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.total_payout_usd = payout_usd
        if virtual_amount is not None:
            self.virtual_currency_awarded = virtual_amount
        self.save(update_fields=['status', 'completed_at', 'total_payout_usd', 'virtual_currency_awarded'])
    
    def mark_expired(self):
        """Mark session as expired."""
        if self.status != 'completed':
            self.status = 'expired'
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at'])
    
    @classmethod
    def get_stats(cls, locker_id: int = None, user_id: int = None, 
                  days: int = 30) -> Dict[str, Any]:
        """
        Get session statistics for analytics dashboard.
        
        Returns comprehensive stats including completion rates, revenue,
        average duration, and user engagement metrics.
        """
        from django.db.models import Q, Count, Sum, Avg, F
        
        # Build base query
        filters = Q(started_at__gte=timezone.now() - timedelta(days=days))
        if locker_id:
            filters &= Q(locker_id=locker_id)
        if user_id:
            filters &= Q(user_id=user_id)
        
        # Get aggregated statistics
        stats = cls.objects.filter(filters).aggregate(
            total_sessions=Count('id'),
            completed_sessions=Count('id', filter=Q(status='completed')),
            expired_sessions=Count('id', filter=Q(status='expired')),
            active_sessions=Count('id', filter=Q(status='active')),
            total_payout=Sum('total_payout_usd'),
            total_virtual=Sum('virtual_currency_awarded'),
            avg_duration=Avg('duration_seconds'),
            avg_payout=Avg('total_payout_usd')
        )
        
        total = stats['total_sessions'] or 0
        completed = stats['completed_sessions'] or 0
        
        # Calculate derived metrics
        completion_rate = (completed / total * 100) if total > 0 else 0
        revenue_per_session = (stats['total_payout'] or Decimal('0')) / total if total > 0 else Decimal('0')
        
        return {
            'period_days': days,
            'total_sessions': total,
            'completed_sessions': completed,
            'expired_sessions': stats['expired_sessions'] or 0,
            'active_sessions': stats['active_sessions'] or 0,
            'completion_rate': round(completion_rate, 2),
            'total_payout_usd': stats['total_payout'] or Decimal('0'),
            'total_virtual_currency': stats['total_virtual'] or Decimal('0'),
            'average_duration_seconds': int(stats['avg_duration'] or 0),
            'average_payout_usd': stats['avg_payout'] or Decimal('0'),
            'revenue_per_session': revenue_per_session,
        }


# ─────────────────────────────────────────────────────────────────
# Offer Cache — Store fetched CPAlead offers
# ─────────────────────────────────────────────────────────────────

class OfferCache(models.Model):
    """
    Cache of CPAlead offers fetched from their JSON API.
    Real CPAlead API: https://api.cpalead.com/offers.php?pub={pub}&user_ip={ip}

    Refreshed periodically by celery task.
    Supports quiz, survey, CPA, CPI, video offer types.
    """
    OFFER_TYPES = [
        ('cpa', _('CPA Offer')),
        ('cpi', _('CPI — App Install')),
        ('cpc', _('CPC — Pay Per Click')),
        ('survey', _('Survey')),
        ('quiz', _('Quiz / Personality Test')),
        ('video', _('Video')),
        ('email_submit', _('Email Submit')),
        ('zip_submit', _('ZIP Submit')),
        ('mobile_content', _('Mobile Content')),
    ]

    offer_id = models.CharField(_("CPAlead Offer ID"), max_length=100, db_index=True)
    offerwall = models.ForeignKey(
        OfferWallConfig, on_delete=models.CASCADE,
        related_name='cached_offers', null=True, blank=True
    )
    offer_type = models.CharField(
        _("Offer Type"), max_length=20, choices=OFFER_TYPES, default='cpa', db_index=True
    )
    title = models.CharField(_("Title"), max_length=300)
    description = models.TextField(blank=True)
    payout_usd = models.DecimalField(
        _("Payout USD"), max_digits=10, decimal_places=4
    )
    # Virtual currency equivalent (auto-calculated)
    payout_virtual = models.DecimalField(
        _("Payout Virtual Currency"), max_digits=14, decimal_places=2, default=0
    )
    icon_url = models.URLField(blank=True)
    offer_url = models.URLField(blank=True)
    # Targeting info from API
    countries = models.JSONField(default=_default_list)
    devices = models.JSONField(default=_default_list)
    os_types = models.JSONField(default=_default_list)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    # Category / quiz support
    category = models.CharField(max_length=100, blank=True)
    is_quiz = models.BooleanField(
        _("Is Quiz Offer"), default=False,
        help_text=_("CPAlead personality/quiz offer type")
    )
    estimated_time_minutes = models.IntegerField(default=5)
    raw_data = models.JSONField(default=_default_dict)
    fetched_at = models.DateTimeField(_("Fetched At"), default=timezone.now)
    expires_at = models.DateTimeField(_("Expires At"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Cached Offer")
        verbose_name_plural = _("Cached Offers")
        ordering = ['-is_featured', '-payout_usd']
        unique_together = [['offerwall', 'offer_id']]
        indexes = [
            models.Index(fields=['offer_type', 'is_active']),
            models.Index(fields=['is_featured', 'payout_usd']),
            models.Index(fields=['fetched_at']),
        ]

    def __str__(self):
        return f"[{self.offer_type}] {self.title} (${self.payout_usd})"

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def is_available_for(self, country: str = '', device: str = '') -> bool:
        """Check if offer is available for a given country/device."""
        if self.countries and country and country.upper() not in self.countries:
            return False
        if self.devices and device and device.lower() not in self.devices:
            return False
        return True
