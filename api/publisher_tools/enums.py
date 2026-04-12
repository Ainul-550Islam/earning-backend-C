# api/publisher_tools/enums.py
"""
Publisher Tools — সব Enum / Choices এক জায়গায়।
Model ও Serializer উভয়তেই এই enums ব্যবহার হবে।
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class PublisherStatus(models.TextChoices):
    PENDING      = 'pending',      _('Pending Review')
    ACTIVE       = 'active',       _('Active')
    SUSPENDED    = 'suspended',    _('Suspended')
    BANNED       = 'banned',       _('Banned')
    UNDER_REVIEW = 'under_review', _('Under Review')


class PublisherTier(models.TextChoices):
    STANDARD   = 'standard',   _('Standard')
    PREMIUM    = 'premium',    _('Premium')
    ENTERPRISE = 'enterprise', _('Enterprise')


class BusinessType(models.TextChoices):
    INDIVIDUAL = 'individual', _('Individual / Freelancer')
    COMPANY    = 'company',    _('Company / LLC')
    AGENCY     = 'agency',     _('Agency')
    NGO        = 'ngo',        _('NGO / Non-profit')
    STARTUP    = 'startup',    _('Startup')


# ──────────────────────────────────────────────────────────────────────────────
# SITE ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class SiteStatus(models.TextChoices):
    PENDING   = 'pending',   _('Pending Verification')
    ACTIVE    = 'active',    _('Active')
    REJECTED  = 'rejected',  _('Rejected')
    SUSPENDED = 'suspended', _('Suspended')
    INACTIVE  = 'inactive',  _('Inactive')


class SiteCategory(models.TextChoices):
    NEWS          = 'news',          _('News & Media')
    BLOG          = 'blog',          _('Blog / Personal')
    ENTERTAINMENT = 'entertainment', _('Entertainment')
    TECHNOLOGY    = 'technology',    _('Technology')
    FINANCE       = 'finance',       _('Finance')
    HEALTH        = 'health',        _('Health & Wellness')
    SPORTS        = 'sports',        _('Sports')
    EDUCATION     = 'education',     _('Education')
    ECOMMERCE     = 'ecommerce',     _('E-Commerce')
    GAMING        = 'gaming',        _('Gaming')
    TRAVEL        = 'travel',        _('Travel')
    FOOD          = 'food',          _('Food & Lifestyle')
    AUTOMOTIVE    = 'automotive',    _('Automotive')
    REAL_ESTATE   = 'real_estate',   _('Real Estate')
    OTHER         = 'other',         _('Other')


class ContentRating(models.TextChoices):
    G    = 'G',    _('G — All Ages')
    PG   = 'PG',   _('PG')
    PG13 = 'PG13', _('PG-13')
    R    = 'R',    _('R — Adults Only')


# ──────────────────────────────────────────────────────────────────────────────
# APP ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class AppPlatform(models.TextChoices):
    ANDROID = 'android', _('Android')
    IOS     = 'ios',     _('iOS')
    BOTH    = 'both',    _('Android + iOS')
    WEB_APP = 'web_app', _('Web App (PWA)')
    OTHER   = 'other',   _('Other')


class AppStatus(models.TextChoices):
    PENDING   = 'pending',   _('Pending Review')
    ACTIVE    = 'active',    _('Active')
    REJECTED  = 'rejected',  _('Rejected')
    SUSPENDED = 'suspended', _('Suspended')
    REMOVED   = 'removed',   _('Removed from Store')


class AppCategory(models.TextChoices):
    GAMES        = 'games',        _('Games')
    TOOLS        = 'tools',        _('Tools & Utilities')
    ENTERTAINMENT= 'entertainment',_('Entertainment')
    SOCIAL       = 'social',       _('Social')
    FINANCE      = 'finance',      _('Finance')
    HEALTH       = 'health',       _('Health & Fitness')
    EDUCATION    = 'education',    _('Education')
    SHOPPING     = 'shopping',     _('Shopping')
    TRAVEL       = 'travel',       _('Travel')
    NEWS         = 'news',         _('News')
    PHOTOGRAPHY  = 'photography',  _('Photography')
    PRODUCTIVITY = 'productivity', _('Productivity')
    LIFESTYLE    = 'lifestyle',    _('Lifestyle')
    SPORTS       = 'sports',       _('Sports')
    OTHER        = 'other',        _('Other')


# ──────────────────────────────────────────────────────────────────────────────
# AD UNIT ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class AdFormat(models.TextChoices):
    BANNER           = 'banner',          _('Banner')
    LEADERBOARD      = 'leaderboard',     _('Leaderboard (728×90)')
    RECTANGLE        = 'rectangle',       _('Rectangle (300×250)')
    SKYSCRAPER       = 'skyscraper',      _('Skyscraper (160×600)')
    BILLBOARD        = 'billboard',       _('Billboard (970×250)')
    NATIVE           = 'native',          _('Native Ad')
    STICKY           = 'sticky',          _('Sticky / Anchor')
    INTERSTITIAL     = 'interstitial',    _('Interstitial (Full Screen)')
    REWARDED_VIDEO   = 'rewarded_video',  _('Rewarded Video')
    APP_OPEN         = 'app_open',        _('App Open Ad')
    OFFERWALL        = 'offerwall',       _('Offerwall')
    INSTREAM_VIDEO   = 'instream_video',  _('In-Stream Video')
    OUTSTREAM_VIDEO  = 'outstream_video', _('Out-Stream Video')
    AUDIO            = 'audio',           _('Audio Ad')
    PLAYABLE         = 'playable',        _('Playable Ad')


class AdUnitStatus(models.TextChoices):
    ACTIVE   = 'active',   _('Active')
    PAUSED   = 'paused',   _('Paused')
    ARCHIVED = 'archived', _('Archived')
    PENDING  = 'pending',  _('Pending Review')


class InventoryType(models.TextChoices):
    SITE = 'site', _('Website')
    APP  = 'app',  _('Mobile App')


# ──────────────────────────────────────────────────────────────────────────────
# PLACEMENT ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class PlacementPosition(models.TextChoices):
    ABOVE_FOLD    = 'above_fold',    _('Above the Fold')
    BELOW_FOLD    = 'below_fold',    _('Below the Fold')
    HEADER        = 'header',        _('Header')
    FOOTER        = 'footer',        _('Footer')
    SIDEBAR_LEFT  = 'sidebar_left',  _('Left Sidebar')
    SIDEBAR_RIGHT = 'sidebar_right', _('Right Sidebar')
    IN_CONTENT    = 'in_content',    _('In-Content')
    BETWEEN_POSTS = 'between_posts', _('Between Posts')
    POPUP         = 'popup',         _('Popup')
    STICKY_BOTTOM = 'sticky_bottom', _('Sticky Bottom')
    STICKY_TOP    = 'sticky_top',    _('Sticky Top')
    APP_START     = 'app_start',     _('App Launch Screen')
    LEVEL_END     = 'level_end',     _('Level / Stage End')
    PAUSE_MENU    = 'pause_menu',    _('Pause Menu')
    EXIT_INTENT   = 'exit_intent',   _('Exit Intent')
    IN_FEED       = 'in_feed',       _('In-Feed')


class RefreshType(models.TextChoices):
    NONE       = 'none',       _('No Refresh')
    TIME_BASED = 'time_based', _('Time-Based Refresh')
    SCROLL     = 'scroll',     _('Scroll-Based Refresh')
    CLICK      = 'click',      _('Click-Based Refresh')


# ──────────────────────────────────────────────────────────────────────────────
# MEDIATION ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class MediationType(models.TextChoices):
    WATERFALL      = 'waterfall',      _('Traditional Waterfall')
    HEADER_BIDDING = 'header_bidding', _('Header Bidding (Prebid)')
    HYBRID         = 'hybrid',         _('Hybrid (Waterfall + Bidding)')


class BiddingType(models.TextChoices):
    CPM          = 'cpm',          _('Fixed CPM')
    DYNAMIC      = 'dynamic',      _('Dynamic eCPM')
    GUARANTEED   = 'guaranteed',   _('Guaranteed Deal')
    PROGRAMMATIC = 'programmatic', _('Programmatic')


class WaterfallItemStatus(models.TextChoices):
    ACTIVE   = 'active',   _('Active')
    PAUSED   = 'paused',   _('Paused')
    DISABLED = 'disabled', _('Disabled')


class BidderType(models.TextChoices):
    PREBID              = 'prebid',              _('Prebid.js Client-Side')
    PREBID_SERVER       = 'prebid_server',       _('Prebid Server')
    AMAZON_TAM          = 'amazon_tam',          _('Amazon TAM')
    GOOGLE_OPEN_BIDDING = 'google_open_bidding', _('Google Open Bidding')
    CUSTOM              = 'custom',              _('Custom RTB')


# ──────────────────────────────────────────────────────────────────────────────
# EARNING ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class EarningGranularity(models.TextChoices):
    HOURLY  = 'hourly',  _('Hourly')
    DAILY   = 'daily',   _('Daily')
    WEEKLY  = 'weekly',  _('Weekly')
    MONTHLY = 'monthly', _('Monthly')


class EarningType(models.TextChoices):
    DISPLAY        = 'display',        _('Display Ad')
    VIDEO          = 'video',          _('Video Ad')
    NATIVE         = 'native',         _('Native Ad')
    INTERSTITIAL   = 'interstitial',   _('Interstitial')
    REWARDED       = 'rewarded',       _('Rewarded Video')
    OFFERWALL      = 'offerwall',      _('Offerwall')
    PROGRAMMATIC   = 'programmatic',   _('Programmatic')
    DIRECT_DEAL    = 'direct_deal',    _('Direct Deal')
    HEADER_BIDDING = 'header_bidding', _('Header Bidding')


class EarningStatus(models.TextChoices):
    ESTIMATED = 'estimated', _('Estimated')
    CONFIRMED = 'confirmed', _('Confirmed')
    ADJUSTED  = 'adjusted',  _('Adjusted')
    FINALIZED = 'finalized', _('Finalized')
    REVERSED  = 'reversed',  _('Reversed')


# ──────────────────────────────────────────────────────────────────────────────
# PAYMENT ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class PaymentMethod(models.TextChoices):
    PAYPAL        = 'paypal',        _('PayPal')
    BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
    WIRE          = 'wire',          _('Wire Transfer')
    CRYPTO_BTC    = 'crypto_btc',    _('Crypto (Bitcoin)')
    CRYPTO_USDT   = 'crypto_usdt',   _('Crypto (USDT)')
    PAYONEER      = 'payoneer',      _('Payoneer')
    BKASH         = 'bkash',         _('bKash')
    NAGAD         = 'nagad',         _('Nagad')
    ROCKET        = 'rocket',        _('Rocket')
    CHECK         = 'check',         _('Paper Check')


class PaymentFrequency(models.TextChoices):
    MONTHLY   = 'monthly',   _('Monthly (Net 30)')
    BIMONTHLY = 'bimonthly', _('Bi-Monthly (Net 15)')
    WEEKLY    = 'weekly',    _('Weekly')
    ON_DEMAND = 'on_demand', _('On Demand')


class InvoiceStatus(models.TextChoices):
    DRAFT      = 'draft',      _('Draft')
    ISSUED     = 'issued',     _('Issued')
    PROCESSING = 'processing', _('Processing Payment')
    PAID       = 'paid',       _('Paid')
    FAILED     = 'failed',     _('Payment Failed')
    DISPUTED   = 'disputed',   _('Disputed')
    CANCELLED  = 'cancelled',  _('Cancelled')


class InvoiceType(models.TextChoices):
    REGULAR    = 'regular',    _('Regular Monthly')
    ON_DEMAND  = 'on_demand',  _('On Demand Request')
    ADJUSTMENT = 'adjustment', _('Adjustment')
    BONUS      = 'bonus',      _('Bonus Payment')


# ──────────────────────────────────────────────────────────────────────────────
# FRAUD / TRAFFIC ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class TrafficType(models.TextChoices):
    BOT               = 'bot',               _('Bot Traffic')
    CRAWLER           = 'crawler',           _('Web Crawler / Spider')
    SCRAPER           = 'scraper',           _('Content Scraper')
    CLICK_FRAUD       = 'click_fraud',       _('Click Fraud')
    CLICK_INJECTION   = 'click_injection',   _('Click Injection')
    CLICK_FLOODING    = 'click_flooding',    _('Click Flooding')
    IMPRESSION_FRAUD  = 'impression_fraud',  _('Impression Fraud')
    AD_STACKING       = 'ad_stacking',       _('Ad Stacking')
    PIXEL_STUFFING    = 'pixel_stuffing',    _('Pixel Stuffing')
    HIDDEN_AD         = 'hidden_ad',         _('Hidden Ad')
    DEVICE_FARM       = 'device_farm',       _('Device Farm')
    EMULATOR          = 'emulator',          _('Emulator / Virtual Device')
    VPN               = 'vpn',               _('VPN Traffic')
    PROXY             = 'proxy',             _('Proxy Traffic')
    TOR               = 'tor',               _('Tor Network')
    GEO_MISMATCH      = 'geo_mismatch',      _('Geo Mismatch')
    SDK_SPOOFING      = 'sdk_spoofing',      _('SDK Spoofing')
    INSTALL_HIJACKING = 'install_hijacking', _('Install Hijacking')
    INCENTIVIZED      = 'incentivized',      _('Incentivized Non-Compliant')
    SUSPICIOUS        = 'suspicious',        _('Suspicious Pattern')
    OTHER             = 'other',             _('Other IVT')


class FraudSeverity(models.TextChoices):
    LOW      = 'low',      _('Low')
    MEDIUM   = 'medium',   _('Medium')
    HIGH     = 'high',     _('High')
    CRITICAL = 'critical', _('Critical')


class FraudAction(models.TextChoices):
    FLAGGED   = 'flagged',   _('Flagged for Review')
    DEDUCTED  = 'deducted',  _('Revenue Deducted')
    WARNED    = 'warned',    _('Publisher Warned')
    SUSPENDED = 'suspended', _('Publisher Suspended')
    BLOCKED   = 'blocked',   _('IP / Device Blocked')
    NO_ACTION = 'no_action', _('No Action Required')
    PENDING   = 'pending',   _('Pending Review')


class ContentQuality(models.TextChoices):
    EXCELLENT = 'excellent', _('Excellent')
    GOOD      = 'good',      _('Good')
    AVERAGE   = 'average',   _('Average')
    POOR      = 'poor',      _('Poor')
    REJECTED  = 'rejected',  _('Rejected / Non-Compliant')


# ──────────────────────────────────────────────────────────────────────────────
# A/B TESTING ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class TestStatus(models.TextChoices):
    DRAFT     = 'draft',     _('Draft')
    RUNNING   = 'running',   _('Running')
    PAUSED    = 'paused',    _('Paused')
    COMPLETED = 'completed', _('Completed')
    CANCELLED = 'cancelled', _('Cancelled')


class TestType(models.TextChoices):
    PLACEMENT  = 'placement',  _('Placement Test')
    AD_FORMAT  = 'ad_format',  _('Ad Format Test')
    FLOOR_PRICE= 'floor_price',_('Floor Price Test')
    WATERFALL  = 'waterfall',  _('Waterfall Test')
    CREATIVE   = 'creative',   _('Creative Test')
    MULTIVARIATE='multivariate',_('Multivariate Test')


class WinnerReason(models.TextChoices):
    HIGHEST_REVENUE  = 'highest_revenue',  _('Highest Revenue')
    HIGHEST_ECPM     = 'highest_ecpm',     _('Highest eCPM')
    HIGHEST_FILL     = 'highest_fill',     _('Highest Fill Rate')
    HIGHEST_CTR      = 'highest_ctr',      _('Highest CTR')
    STATISTICAL_SIG  = 'statistical_sig',  _('Statistical Significance')
    MANUAL           = 'manual',           _('Manual Selection')


# ──────────────────────────────────────────────────────────────────────────────
# VERIFICATION ENUMS
# ──────────────────────────────────────────────────────────────────────────────

class VerificationMethod(models.TextChoices):
    ADS_TXT    = 'ads_txt',    _('ads.txt File')
    META_TAG   = 'meta_tag',   _('HTML Meta Tag')
    DNS_RECORD = 'dns_record', _('DNS TXT Record')
    FILE       = 'file',       _('HTML File Upload')
    API        = 'api',        _('API Verification')
    MANUAL     = 'manual',     _('Manual Admin Verification')


class VerificationStatus(models.TextChoices):
    PENDING  = 'pending',  _('Pending')
    VERIFIED = 'verified', _('Verified')
    FAILED   = 'failed',   _('Failed')
    EXPIRED  = 'expired',  _('Expired')
