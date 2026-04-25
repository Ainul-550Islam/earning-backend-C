"""
api/ad_networks/choices.py
Centralized choice definitions for Ad Networks module
SaaS-ready with tenant support
"""

from django.utils.translation import gettext_lazy as _


# ==================== NETWORK CHOICES ====================

class NetworkCategory:
    """Network category choices"""
    OFFERWALL = 'offerwall'
    SURVEY = 'survey'
    VIDEO = 'video'
    GAMING = 'gaming'
    APP_INSTALL = 'app_install'
    CASHBACK = 'cashback'
    CPI_CPA = 'cpi_cpa'
    CPE = 'cpe'
    OTHER = 'other'
    
    CHOICES = (
        (OFFERWALL, _('Offerwall')),
        (SURVEY, _('Survey')),
        (VIDEO, _('Video/Ads')),
        (GAMING, _('Gaming')),
        (APP_INSTALL, _('App Install')),
        (CASHBACK, _('Cashback')),
        (CPI_CPA, _('CPI/CPA')),
        (CPE, _('CPE (Cost Per Engagement)')),
        (OTHER, _('Other')),
    )


class CountrySupport:
    """Country support level choices"""
    GLOBAL = 'global'
    TIER1 = 'tier1'
    TIER2 = 'tier2'
    TIER3 = 'tier3'
    BD_ONLY = 'bd_only'
    INDIAN_SUB = 'indian_sub'
    
    CHOICES = (
        (GLOBAL, _('Global')),
        (TIER1, _('Tier 1 (US, UK, CA, AU)')),
        (TIER2, _('Tier 2 (EU, Middle East)')),
        (TIER3, _('Tier 3 (Asia, Africa, South America)')),
        (BD_ONLY, _('Bangladesh Only')),
        (INDIAN_SUB, _('Indian Subcontinent')),
    )


class NetworkStatus:
    """Network status choices"""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    MAINTENANCE = 'maintenance'
    SUSPENDED = 'suspended'
    
    CHOICES = (
        (ACTIVE, _('Active')),
        (INACTIVE, _('Inactive')),
        (MAINTENANCE, _('Under Maintenance')),
        (SUSPENDED, _('Suspended')),
    )


# ==================== OFFER CHOICES ====================

class OfferStatus:
    """Offer status choices"""
    ACTIVE = 'active'
    PAUSED = 'paused'
    EXPIRED = 'expired'
    PENDING_REVIEW = 'pending_review'
    REJECTED = 'rejected'
    COMPLETED = 'completed'
    
    CHOICES = (
        (ACTIVE, _('Active')),
        (PAUSED, _('Paused')),
        (EXPIRED, _('Expired')),
        (PENDING_REVIEW, _('Pending Review')),
        (REJECTED, _('Rejected')),
        (COMPLETED, _('Completed')),
    )


class OfferCategoryType:
    """Offer category type choices"""
    SURVEY = 'survey'
    OFFER = 'offer'
    VIDEO = 'video'
    GAME = 'game'
    APP_INSTALL = 'app_install'
    QUIZ = 'quiz'
    TASK = 'task'
    SIGNUP = 'signup'
    SHOPPING = 'shopping'
    CASHBACK = 'cashback'
    OTHER = 'other'
    
    CHOICES = (
        (SURVEY, _('Survey')),
        (OFFER, _('Offer')),
        (VIDEO, _('Video')),
        (GAME, _('Game')),
        (APP_INSTALL, _('App Install')),
        (QUIZ, _('Quiz')),
        (TASK, _('Task')),
        (SIGNUP, _('Signup')),
        (SHOPPING, _('Shopping')),
        (CASHBACK, _('Cashback')),
        (OTHER, _('Other')),
    )


class DifficultyLevel:
    """Offer difficulty levels"""
    VERY_EASY = 'very_easy'
    EASY = 'easy'
    MEDIUM = 'medium'
    HARD = 'hard'
    VERY_HARD = 'very_hard'
    
    CHOICES = (
        (VERY_EASY, _('Very Easy')),
        (EASY, _('Easy')),
        (MEDIUM, _('Medium')),
        (HARD, _('Hard')),
        (VERY_HARD, _('Very Hard')),
    )


class DeviceType:
    """Device type choices"""
    ANY = 'any'
    MOBILE = 'mobile'
    TABLET = 'tablet'
    DESKTOP = 'desktop'
    ANDROID = 'android'
    IOS = 'ios'
    
    CHOICES = (
        (ANY, _('Any Device')),
        (MOBILE, _('Mobile Only')),
        (TABLET, _('Tablet Only')),
        (DESKTOP, _('Desktop Only')),
        (ANDROID, _('Android Only')),
        (IOS, _('iOS Only')),
    )


class GenderTargeting:
    """Gender targeting choices"""
    ANY = 'any'
    MALE = 'male'
    FEMALE = 'female'
    
    CHOICES = (
        (ANY, _('Any Gender')),
        (MALE, _('Male Only')),
        (FEMALE, _('Female Only')),
    )


class AgeGroup:
    """Age group choices"""
    TEEN = '13-17'
    YOUNG_ADULT = '18-24'
    ADULT = '25-34'
    MIDDLE_AGE = '35-44'
    SENIOR_ADULT = '45-54'
    ELDERLY = '55+'
    ANY = 'any'
    
    CHOICES = (
        (TEEN, _('Teen (13-17)')),
        (YOUNG_ADULT, _('Young Adult (18-24)')),
        (ADULT, _('Adult (25-34)')),
        (MIDDLE_AGE, _('Middle Age (35-44)')),
        (SENIOR_ADULT, _('Senior Adult (45-54)')),
        (ELDERLY, _('Elderly (55+)')),
        (ANY, _('Any Age')),
    )


# ==================== CONVERSION CHOICES ====================

class ConversionStatus:
    """Conversion status choices"""
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    FRAUD = 'fraud'
    REVERSED = 'reversed'
    CHARGEBACK = 'chargeback'
    DISPUTED = 'disputed'
    PAID = 'paid'
    
    CHOICES = (
        (PENDING, _('Pending Verification')),
        (APPROVED, _('Approved')),
        (REJECTED, _('Rejected')),
        (FRAUD, _('Fraud Detected')),
        (REVERSED, _('Reversed')),
        (CHARGEBACK, _('Chargeback')),
        (DISPUTED, _('Disputed')),
        (PAID, _('Paid')),
    )


class RiskLevel:
    """Risk level choices for fraud detection"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    
    CHOICES = (
        (LOW, _('Low Risk')),
        (MEDIUM, _('Medium Risk')),
        (HIGH, _('High Risk')),
    )


# ==================== USER ENGAGEMENT CHOICES ====================

class EngagementStatus:
    """User engagement status choices"""
    CLICKED = 'clicked'
    STARTED = 'started'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    CANCELED = 'canceled'
    EXPIRED = 'expired'
    
    CHOICES = (
        (CLICKED, _('Clicked')),
        (STARTED, _('Started')),
        (IN_PROGRESS, _('In Progress')),
        (COMPLETED, _('Completed')),
        (PENDING, _('Pending Verification')),
        (APPROVED, _('Approved')),
        (REJECTED, _('Rejected')),
        (CANCELED, _('Canceled')),
        (EXPIRED, _('Expired')),
    )


class RejectionReason:
    """Rejection reason choices"""
    FRAUD = 'fraud'
    INCOMPLETE = 'incomplete'
    QUALITY = 'quality'
    DUPLICATE = 'duplicate'
    TIMEOUT = 'timeout'
    INVALID = 'invalid'
    OTHER = 'other'
    
    CHOICES = (
        (FRAUD, _('Fraud Detected')),
        (INCOMPLETE, _('Incomplete Action')),
        (QUALITY, _('Low Quality')),
        (DUPLICATE, _('Duplicate')),
        (TIMEOUT, _('Time Limit Exceeded')),
        (INVALID, _('Invalid Data')),
        (OTHER, _('Other')),
    )


# ==================== PAYMENT CHOICES ====================

class PaymentMethod:
    """Payment method choices"""
    PAYPAL = 'paypal'
    BANK = 'bank'
    CRYPTO = 'crypto'
    SKRILL = 'skrill'
    PAYONEER = 'payoneer'
    WIRE = 'wire'
    BKASH = 'bkash'
    NAGAD = 'nagad'
    ROCKET = 'rocket'
    UPAY = 'upay'
    
    CHOICES = (
        (PAYPAL, _('PayPal')),
        (BANK, _('Bank Transfer')),
        (CRYPTO, _('Cryptocurrency')),
        (SKRILL, _('Skrill')),
        (PAYONEER, _('Payoneer')),
        (WIRE, _('Wire Transfer')),
        (BKASH, _('bKash')),
        (NAGAD, _('Nagad')),
        (ROCKET, _('Rocket')),
        (UPAY, _('Upay')),
    )


# ==================== OFFER WALL CHOICES ====================

class WallType:
    """Offer wall type choices"""
    MAIN = 'main'
    SURVEY = 'survey'
    VIDEO = 'video'
    GAME = 'game'
    APP = 'app'
    FEATURED = 'featured'
    TRENDING = 'trending'
    
    CHOICES = (
        (MAIN, _('Main Offerwall')),
        (SURVEY, _('Survey Wall')),
        (VIDEO, _('Video Wall')),
        (GAME, _('Game Wall')),
        (APP, _('App Install Wall')),
        (FEATURED, _('Featured Offers')),
        (TRENDING, _('Trending Offers')),
    )


# ==================== NETWORK TYPE CHOICES ====================
# 80+ Network Types (from existing models)

class NetworkType:
    """Network type choices for 80+ networks"""
    
    # Basic Networks (1-6)
    ADMOB = 'admob'
    UNITY = 'unity'
    IRONSOURCE = 'ironsource'
    APPLOVIN = 'applovin'
    TAPJOY = 'tapjoy'
    VUNGLE = 'vungle'
    
    # Top Offerwalls (7-26)
    ADSCEND = 'adscend'
    OFFERTORO = 'offertoro'
    ADGEM = 'adgem'
    AYETSTUDIOS = 'ayetstudios'
    LOOTABLY = 'lootably'
    REVENUEUNIVERSE = 'revenueuniverse'
    ADGATE = 'adgate'
    CPALEAD = 'cpalead'
    ADWORKMEDIA = 'adworkmedia'
    WANNAADS = 'wannads'
    PERSONALY = 'personaly'
    KIWIWALL = 'kiwiwall'
    MONLIX = 'monlix'
    NOTIK = 'notik'
    OFFERDADDY = 'offerdaddy'
    OFFERTOWN = 'offertown'
    ADLOCKMEDIA = 'adlockmedia'
    OFFERWALLPRO = 'offerwallpro'
    WALLADS = 'wallads'
    WALLPORT = 'wallport'
    WALLTORO = 'walltoro'
    
    # Survey Specialists (27-41)
    POLLFISH = 'pollfish'
    CPXRESEARCH = 'cpxresearch'
    BITLABS = 'bitlabs'
    INBRAIN = 'inbrain'
    THEOREMREACH = 'theoremreach'
    YOURSURVEYS = 'yoursurveys'
    SURVEYSAVVY = 'surveysavvy'
    OPINIONWORLD = 'opinionworld'
    TOLUNA = 'toluna'
    SURVEYMONKEY = 'surveymonkey'
    SWAGBUCKS = 'swagbucks'
    PRIZEREBEL = 'prizerebel'
    GRABPOINTS = 'grabpoints'
    INSTAGC = 'instagc'
    POINTS2SHOP = 'points2shop'
    
    # Video & Easy Tasks (42-56)
    LOOTTV = 'loottv'
    HIDEOUTTV = 'hideouttv'
    REWARDRACK = 'rewardrack'
    EARNHONEY = 'earnhoney'
    REWARDXP = 'rewardxp'
    IDLEEMPIRE = 'idleempire'
    GAIN = 'gain'
    GRINDABUCK = 'grindabuck'
    TIMEBUCKS = 'timebucks'
    CLIXSENSE = 'clixsense'
    NEOBUX = 'neobux'
    PROBUX = 'probux'
    CLIXWALL = 'clixwall'
    FYBER = 'fyber'
    OFFERSTATION = 'offerstation'
    
    # Gaming & App Install (57-70)
    CHARTBOOST = 'chartboost'
    SUPERSONIC = 'supersonic'
    APPNEXT = 'appnext'
    DIGITALTURBINE = 'digitalturbine'
    GLISPA = 'glispa'
    ADCOLONY = 'adcolony'
    INMOBI = 'inmobi'
    MOPUB = 'mopub'
    PANGLE = 'pangle'
    MINTTEGRAL = 'mintegral'
    OGURY = 'ogury'
    VERIZONMEDIA = 'verizonmedia'
    SMAATO = 'smaato'
    MOBILEFUSE = 'mobilefuse'
    
    # More Networks (71-80)
    LEADBOLT = 'leadbolt'
    STARTAPP = 'startapp'
    MEDIABRIX = 'mediabrix'
    NATIVEX = 'nativex'
    HEYZAP = 'heyzap'
    KIDOZ = 'kidoz'
    POKKT = 'pokkt'
    YOUAPPI = 'youappi'
    AMPIRI = 'ampiri'
    ADINCUBE = 'adincube'
    
    # Future Expansion (81-90)
    CUSTOM1 = 'custom1'
    CUSTOM2 = 'custom2'
    CUSTOM3 = 'custom3'
    CUSTOM4 = 'custom4'
    CUSTOM5 = 'custom5'
    CUSTOM6 = 'custom6'
    CUSTOM7 = 'custom7'
    CUSTOM8 = 'custom8'
    CUSTOM9 = 'custom9'
    CUSTOM10 = 'custom10'
    
    CHOICES = (
        # Basic Networks
        (ADMOB, _('Google AdMob')),
        (UNITY, _('Unity Ads')),
        (IRONSOURCE, _('IronSource')),
        (APPLOVIN, _('AppLovin')),
        (TAPJOY, _('Tapjoy')),
        (VUNGLE, _('Vungle')),
        
        # Top Offerwalls
        (ADSCEND, _('Adscend Media')),
        (OFFERTORO, _('OfferToro')),
        (ADGEM, _('AdGem')),
        (AYETSTUDIOS, _('Ayetstudios')),
        (LOOTABLY, _('Lootably')),
        (REVENUEUNIVERSE, _('Revenue Universe')),
        (ADGATE, _('AdGate Media')),
        (CPALEAD, _('CPAlead')),
        (ADWORKMEDIA, _('AdWork Media')),
        (WANNAADS, _('Wannads')),
        (PERSONALY, _('Persona.ly')),
        (KIWIWALL, _('KiwiWall')),
        (MONLIX, _('Monlix')),
        (NOTIK, _('Notik')),
        (OFFERDADDY, _('OfferDaddy')),
        (OFFERTOWN, _('OfferTown')),
        (ADLOCKMEDIA, _('AdLock Media')),
        (OFFERWALLPRO, _('Offerwall.pro')),
        (WALLADS, _('WallAds')),
        (WALLPORT, _('Wallport')),
        (WALLTORO, _('WallToro')),
        
        # Survey Specialists
        (POLLFISH, _('Pollfish')),
        (CPXRESEARCH, _('CPX Research')),
        (BITLABS, _('BitLabs')),
        (INBRAIN, _('InBrain.ai')),
        (THEOREMREACH, _('TheoremReach')),
        (YOURSURVEYS, _('YourSurveys')),
        (SURVEYSAVVY, _('SurveySavvy')),
        (OPINIONWORLD, _('OpinionWorld')),
        (TOLUNA, _('Toluna')),
        (SURVEYMONKEY, _('SurveyMonkey')),
        (SWAGBUCKS, _('Swagbucks')),
        (PRIZEREBEL, _('PrizeRebel')),
        (GRABPOINTS, _('GrabPoints')),
        (INSTAGC, _('InstaGC')),
        (POINTS2SHOP, _('Points2Shop')),
        
        # Video & Easy Tasks
        (LOOTTV, _('Loot.tv')),
        (HIDEOUTTV, _('Hideout.tv')),
        (REWARDRACK, _('RewardRack')),
        (EARNHONEY, _('EarnHoney')),
        (REWARDXP, _('RewardXP')),
        (IDLEEMPIRE, _('Idle-Empire')),
        (GAIN, _('Gain.gg')),
        (GRINDABUCK, _('GrindaBuck')),
        (TIMEBUCKS, _('TimeBucks')),
        (CLIXSENSE, _('ClixSense')),
        (NEOBUX, _('NeoBux')),
        (PROBUX, _('ProBux')),
        (CLIXWALL, _('ClixWall')),
        (FYBER, _('Fyber')),
        (OFFERSTATION, _('OfferStation')),
        
        # Gaming & App Install
        (CHARTBOOST, _('Chartboost')),
        (SUPERSONIC, _('Supersonic')),
        (APPNEXT, _('AppNext')),
        (DIGITALTURBINE, _('Digital Turbine')),
        (GLISPA, _('Glispa')),
        (ADCOLONY, _('AdColony')),
        (INMOBI, _('InMobi')),
        (MOPUB, _('MoPub')),
        (PANGLE, _('Pangle (by TikTok)')),
        (MINTTEGRAL, _('Mintegral')),
        (OGURY, _('Ogury')),
        (VERIZONMEDIA, _('Verizon Media')),
        (SMAATO, _('Smaato')),
        (MOBILEFUSE, _('MobileFuse')),
        
        # More Networks
        (LEADBOLT, _('Leadbolt')),
        (STARTAPP, _('StartApp')),
        (MEDIABRIX, _('Mediabrix')),
        (NATIVEX, _('NativeX')),
        (HEYZAP, _('Heyzap')),
        (KIDOZ, _('Kidoz')),
        (POKKT, _('Pokkt')),
        (YOUAPPI, _('YouAppi')),
        (AMPIRI, _('Ampiri')),
        (ADINCUBE, _('AdinCube')),
        
        # Future Expansion
        (CUSTOM1, _('Custom Network 1')),
        (CUSTOM2, _('Custom Network 2')),
        (CUSTOM3, _('Custom Network 3')),
        (CUSTOM4, _('Custom Network 4')),
        (CUSTOM5, _('Custom Network 5')),
        (CUSTOM6, _('Custom Network 6')),
        (CUSTOM7, _('Custom Network 7')),
        (CUSTOM8, _('Custom Network 8')),
        (CUSTOM9, _('Custom Network 9')),
        (CUSTOM10, _('Custom Network 10')),
    )


# ==================== HELPER FUNCTIONS ====================

def get_network_category_choices():
    """Get network category choices"""
    return NetworkCategory.CHOICES


def get_country_support_choices():
    """Get country support choices"""
    return CountrySupport.CHOICES


def get_offer_status_choices():
    """Get offer status choices"""
    return OfferStatus.CHOICES


def get_conversion_status_choices():
    """Get conversion status choices"""
    return ConversionStatus.CHOICES


def get_network_type_choices():
    """Get network type choices"""
    return NetworkType.CHOICES


def get_payment_method_choices():
    """Get payment method choices"""
    return PaymentMethod.CHOICES


# ==================== VALIDATION HELPERS ====================

def is_valid_network_type(network_type):
    """Check if network type is valid"""
    valid_types = [choice[0] for choice in NetworkType.CHOICES]
    return network_type in valid_types


def is_valid_category(category):
    """Check if category is valid"""
    valid_categories = [choice[0] for choice in NetworkCategory.CHOICES]
    return category in valid_categories


def is_valid_country_support(country_support):
    """Check if country support is valid"""
    valid_support = [choice[0] for choice in CountrySupport.CHOICES]
    return country_support in valid_support


def is_valid_offer_status(status):
    """Check if offer status is valid"""
    valid_statuses = [choice[0] for choice in OfferStatus.CHOICES]
    return status in valid_statuses


def is_valid_conversion_status(status):
    """Check if conversion status is valid"""
    valid_statuses = [choice[0] for choice in ConversionStatus.CHOICES]
    return status in valid_statuses


class RewardStatus:
    PENDING = 'pending'
    APPROVED = 'approved'
    PAID = 'paid'
    REJECTED = 'rejected'
    REVERSED = 'reversed'
    
    CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (PAID, 'Paid'),
        (REJECTED, 'Rejected'),
        (REVERSED, 'Reversed'),
    ]

Difficulty = DifficultyLevel  # alias
