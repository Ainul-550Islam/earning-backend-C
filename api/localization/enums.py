# enums.py — Python Enums for type-safe usage in code
from enum import Enum, auto


class TextDirection(str, Enum):
    LTR  = 'ltr'
    RTL  = 'rtl'
    AUTO = 'auto'


class TranslationSource(str, Enum):
    MANUAL = 'manual'
    AUTO   = 'auto'
    IMPORT = 'import'
    API    = 'api'
    MEMORY = 'memory'
    MACHINE = 'machine'


class QualityScore(str, Enum):
    EXCELLENT  = 'excellent'
    GOOD       = 'good'
    FAIR       = 'fair'
    POOR       = 'poor'
    UNREVIEWED = 'unreviewed'

    @property
    def threshold(self):
        return {'excellent': 90, 'good': 70, 'fair': 50, 'poor': 0, 'unreviewed': -1}[self.value]


class Priority(str, Enum):
    CRITICAL = 'critical'
    HIGH     = 'high'
    NORMAL   = 'normal'
    LOW      = 'low'

    @property
    def sort_key(self):
        return {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}[self.value]


class TranslationProvider(str, Enum):
    GOOGLE = 'google'
    DEEPL  = 'deepl'
    AZURE  = 'azure'
    AMAZON = 'amazon'
    OPENAI = 'openai'
    MANUAL = 'manual'
    MEMORY = 'memory'


class ExportFormat(str, Enum):
    JSON  = 'json'
    PO    = 'po'
    XLIFF = 'xliff'
    CSV   = 'csv'
    TMX   = 'tmx'


class WorkflowStatus(str, Enum):
    PENDING     = 'pending'
    IN_PROGRESS = 'in_progress'
    REVIEW      = 'review'
    REVISION    = 'revision'
    APPROVED    = 'approved'
    PUBLISHED   = 'published'
    REJECTED    = 'rejected'
    ON_HOLD     = 'on_hold'
    CANCELLED   = 'cancelled'


class AnalyticsEvent(str, Enum):
    TRANSLATION_REQUESTED  = 'translation_requested'
    TRANSLATION_MISSING    = 'translation_missing'
    LANGUAGE_SWITCH        = 'language_switch'
    CURRENCY_CONVERTED     = 'currency_converted'
    GEOLOCATION_LOOKUP     = 'geolocation_lookup'
    USER_PREF_UPDATED      = 'user_preference_updated'
    REGION_DETECTED        = 'region_detected'
    PACK_DOWNLOADED        = 'language_pack_downloaded'
    OFFER_VIEWED           = 'offer_viewed'


class GeoIPSource(str, Enum):
    MAXMIND    = 'maxmind'
    IPINFO     = 'ipinfo'
    IP2LOCATION = 'ip2location'
    IPAPI      = 'ipapi'
    MANUAL     = 'manual'


class CalendarSystem(str, Enum):
    GREGORIAN    = 'gregorian'
    ISLAMIC      = 'islamic'
    ISLAMIC_CIVIL = 'islamic_civil'
    PERSIAN      = 'persian'
    HEBREW       = 'hebrew'
    BUDDHIST     = 'buddhist'
    JAPANESE     = 'japanese'
    CHINESE      = 'chinese'


class Continent(str, Enum):
    AFRICA        = 'AF'
    ASIA          = 'AS'
    EUROPE        = 'EU'
    NORTH_AMERICA = 'NA'
    SOUTH_AMERICA = 'SA'
    OCEANIA       = 'OC'
    ANTARCTICA    = 'AN'


class MeasurementSystem(str, Enum):
    METRIC   = 'metric'
    IMPERIAL = 'imperial'
    US       = 'us_customary'
