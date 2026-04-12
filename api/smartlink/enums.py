from enum import Enum, IntEnum


class TargetingRuleLogic(str, Enum):
    AND = 'AND'
    OR = 'OR'


class OfferSelectionReason(str, Enum):
    WEIGHTED_RANDOM = 'weighted_random'
    EPC_OPTIMIZED = 'epc_optimized'
    ROUND_ROBIN = 'round_robin'
    PRIORITY = 'priority'
    FALLBACK = 'fallback'
    AB_TEST_VARIANT = 'ab_test_variant'
    MANUAL_OVERRIDE = 'manual_override'


class ClickStatus(str, Enum):
    VALID = 'valid'
    DUPLICATE = 'duplicate'
    FRAUD = 'fraud'
    BOT = 'bot'
    CAPPED = 'capped'
    NO_OFFER = 'no_offer'


class RedirectStatus(str, Enum):
    SUCCESS = 'success'
    FALLBACK = 'fallback'
    NO_MATCH = 'no_match'
    BLOCKED = 'blocked'
    ERROR = 'error'


class FraudSignalType(str, Enum):
    HIGH_VELOCITY = 'high_velocity'
    DATACENTER_IP = 'datacenter_ip'
    BOT_UA = 'bot_ua'
    PROXY_VPN = 'proxy_vpn'
    INVALID_UA = 'invalid_ua'
    HEADLESS_BROWSER = 'headless_browser'
    KNOWN_BAD_IP = 'known_bad_ip'
    SUSPICIOUS_PATTERN = 'suspicious_pattern'


class ABTestVariantType(str, Enum):
    CONTROL = 'control'
    VARIANT_A = 'variant_a'
    VARIANT_B = 'variant_b'
    VARIANT_C = 'variant_c'


class SmartLinkStatus(str, Enum):
    ACTIVE = 'active'
    PAUSED = 'paused'
    ARCHIVED = 'archived'
    DRAFT = 'draft'


class TaskPriority(IntEnum):
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class FraudAction(str, Enum):
    BLOCK = 'block'
    FLAG = 'flag'
    ALLOW = 'allow'
    CHALLENGE = 'challenge'
    REDIRECT = 'redirect'
