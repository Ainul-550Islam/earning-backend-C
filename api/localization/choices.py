# choices.py — All Django model choices in one place
from django.utils.translation import gettext_lazy as _

# ── Language ──────────────────────────────────────────────────────
TEXT_DIRECTION_CHOICES = [
    ('ltr', _('Left to Right')),
    ('rtl', _('Right to Left')),
    ('auto', _('Auto-detect')),
]
SCRIPT_CODE_CHOICES = [
    ('Latn', _('Latin')), ('Arab', _('Arabic')), ('Beng', _('Bengali')),
    ('Deva', _('Devanagari')), ('Hans', _('Simplified Chinese')),
    ('Hant', _('Traditional Chinese')), ('Cyrl', _('Cyrillic')),
    ('Hebr', _('Hebrew')), ('Jpan', _('Japanese')), ('Hang', _('Hangul')),
    ('Thai', _('Thai')), ('Taml', _('Tamil')), ('Ethi', _('Ethiopic')),
    ('Grek', _('Greek')), ('Mlym', _('Malayalam')),
]

# ── Translation ───────────────────────────────────────────────────
TRANSLATION_SOURCE_CHOICES = [
    ('manual', _('Manual')), ('auto', _('Auto-translated')),
    ('import', _('Imported')), ('api', _('API')),
    ('memory', _('Translation Memory')), ('machine', _('Machine')),
]
QUALITY_SCORE_CHOICES = [
    ('excellent', _('Excellent (90-100%)')), ('good', _('Good (70-89%)')),
    ('fair', _('Fair (50-69%)')), ('poor', _('Poor (<50%)')),
    ('unreviewed', _('Unreviewed')),
]
PRIORITY_CHOICES = [
    ('critical', _('Critical')), ('high', _('High')),
    ('normal', _('Normal')), ('low', _('Low')),
]
REVIEW_STATUS_CHOICES = [
    ('pending', _('Pending')), ('reviewed', _('Reviewed')),
    ('approved', _('Approved')), ('rejected', _('Rejected')),
]

# ── Currency ──────────────────────────────────────────────────────
SYMBOL_POSITION_CHOICES = [
    ('before', _('Before amount ($100)')),
    ('after', _('After amount (100$)')),
]
ROUNDING_RULE_CHOICES = [
    ('round', _('Round')), ('floor', _('Floor')), ('ceil', _('Ceiling')),
]
EXCHANGE_SOURCE_CHOICES = [
    ('manual', _('Manual')),
    ('openexchangerates', _('Open Exchange Rates')),
    ('fixer', _('Fixer.io')),
    ('currencylayer', _('CurrencyLayer')),
    ('xe', _('XE.com')),
    ('ecb', _('European Central Bank')),
    ('bangladesh_bank', _('Bangladesh Bank')),
    ('fed', _('Federal Reserve')),
    ('coinbase', _('Coinbase')),
    ('binance', _('Binance')),
]

# ── GeoIP ─────────────────────────────────────────────────────────
GEOIP_SOURCE_CHOICES = [
    ('maxmind', _('MaxMind GeoIP2')),
    ('ipinfo', _('IPinfo')),
    ('ip2location', _('IP2Location')),
    ('ipapi', _('ip-api.com')),
    ('manual', _('Manual')),
]

# ── Region ────────────────────────────────────────────────────────
REGION_TYPE_CHOICES = [
    ('continent', _('Continent')), ('subregion', _('Subregion')),
    ('country', _('Country')), ('state', _('State/Province')),
    ('district', _('District')), ('city', _('City')),
    ('neighborhood', _('Neighborhood')),
]

# ── Content ───────────────────────────────────────────────────────
IMAGE_TYPE_CHOICES = [
    ('banner', _('Banner')), ('thumbnail', _('Thumbnail')),
    ('hero', _('Hero')), ('icon', _('Icon')),
    ('avatar', _('Avatar')), ('background', _('Background')),
]
CALENDAR_SYSTEM_CHOICES = [
    ('gregorian', _('Gregorian')), ('islamic', _('Islamic/Hijri')),
    ('islamic_civil', _('Islamic Civil')), ('persian', _('Persian')),
    ('hebrew', _('Hebrew')), ('buddhist', _('Buddhist')),
    ('japanese', _('Japanese')), ('chinese', _('Chinese Lunisolar')),
]

# ── Workflow ──────────────────────────────────────────────────────
WORKFLOW_STATUS_CHOICES = [
    ('pending', _('Pending')), ('in_progress', _('In Progress')),
    ('review', _('Under Review')), ('revision', _('Needs Revision')),
    ('approved', _('Approved')), ('published', _('Published')),
    ('rejected', _('Rejected')), ('on_hold', _('On Hold')),
    ('cancelled', _('Cancelled')),
]
STEP_TYPE_CHOICES = [
    ('translation', _('Translation')), ('review', _('Review')),
    ('proofreading', _('Proofreading')), ('approval', _('Approval')),
    ('dtp', _('Desktop Publishing')), ('qa', _('QA')),
    ('publishing', _('Publishing')),
]

# ── Auto-translate provider ───────────────────────────────────────
AUTO_TRANSLATE_PROVIDER_CHOICES = [
    ('google', _('Google Translate')),
    ('deepl', _('DeepL')),
    ('azure', _('Microsoft Azure')),
    ('amazon', _('Amazon Translate')),
    ('openai', _('OpenAI GPT')),
]

# ── Language pack format ─────────────────────────────────────────
PACK_FORMAT_CHOICES = [
    ('json', 'JSON'), ('fluent', 'Mozilla Fluent (.ftl)'),
    ('po', 'Gettext PO'), ('xliff', 'XLIFF'), ('icu', 'ICU Message Format'),
]
PACK_STATUS_CHOICES = [
    ('draft', _('Draft')), ('building', _('Building')),
    ('ready', _('Ready')), ('published', _('Published')),
    ('deprecated', _('Deprecated')),
]

# ── Continent codes ───────────────────────────────────────────────
CONTINENT_CHOICES = [
    ('AF', _('Africa')), ('AS', _('Asia')), ('EU', _('Europe')),
    ('NA', _('North America')), ('SA', _('South America')),
    ('OC', _('Oceania')), ('AN', _('Antarctica')),
]

# ── Measurement system ────────────────────────────────────────────
MEASUREMENT_CHOICES = [
    ('metric', _('Metric')), ('imperial', _('Imperial')),
    ('us_customary', _('US Customary')),
]

# ── Driving side ──────────────────────────────────────────────────
DRIVING_SIDE_CHOICES = [
    ('left', _('Left-hand traffic')),
    ('right', _('Right-hand traffic')),
]
