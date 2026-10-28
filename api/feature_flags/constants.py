"""
Constants for Feature Flags & A/B Testing.
"""
from enum import Enum


class FlagType(Enum):
    """Flag type constants."""
    BOOLEAN = 'boolean'
    STRING = 'string'
    NUMBER = 'number'
    JSON = 'json'


class FlagStatus(Enum):
    """Flag status constants."""
    DRAFT = 'draft'
    ACTIVE = 'active'
    PAUSED = 'paused'
    ARCHIVED = 'archived'


class ExperimentStatus(Enum):
    """Experiment status constants."""
    DRAFT = 'draft'
    RUNNING = 'running'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class RuleType(Enum):
    """Rule type constants."""
    USER_ID = 'user_id'
    EMAIL = 'email'
    SEGMENT = 'segment'
    ATTRIBUTE = 'attribute'
    PERCENTAGE = 'percentage'
    CUSTOM = 'custom'


class RuleOperator(Enum):
    """Rule operator constants."""
    EQUALS = 'equals'
    NOT_EQUALS = 'not_equals'
    CONTAINS = 'contains'
    NOT_CONTAINS = 'not_contains'
    STARTS_WITH = 'starts_with'
    ENDS_WITH = 'ends_with'
    GREATER_THAN = 'greater_than'
    LESS_THAN = 'less_than'
    IN = 'in'
    NOT_IN = 'not_in'


# Default values
DEFAULT_FLAG_TYPE = FlagType.BOOLEAN.value
DEFAULT_FLAG_STATUS = FlagStatus.DRAFT.value
DEFAULT_EXPERIMENT_STATUS = ExperimentStatus.DRAFT.value
DEFAULT_ROLLOUT_PERCENTAGE = 0
DEFAULT_MIN_SAMPLE_SIZE = 100
DEFAULT_SIGNIFICANCE_THRESHOLD = 0.95

# Configuration limits
MAX_FLAG_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 10000
MAX_RULE_PRIORITY = 1000
MAX_VARIANT_WEIGHT = 100

# Cache configuration
DEFAULT_CACHE_TIMEOUT = 300  # 5 minutes
FLAG_CACHE_PREFIX = 'flag_enabled:'
EXPERIMENT_CACHE_PREFIX = 'experiment:'

# Environment names
ENVIRONMENT_DEVELOPMENT = 'development'
ENVIRONMENT_STAGING = 'staging'
ENVIRONMENT_PRODUCTION = 'production'

# Error codes
ERROR_FLAG_NOT_FOUND = 'FLAG_NOT_FOUND'
ERROR_FLAG_DISABLED = 'FLAG_DISABLED'
ERROR_INVALID_FLAG_TYPE = 'INVALID_FLAG_TYPE'
ERROR_INVALID_CONTEXT = 'INVALID_CONTEXT'
ERROR_EXPERIMENT_NOT_FOUND = 'EXPERIMENT_NOT_FOUND'
ERROR_EXPERIMENT_NOT_ACTIVE = 'EXPERIMENT_NOT_ACTIVE'
ERROR_INVALID_VARIANT = 'INVALID_VARIANT'

# Success messages
SUCCESS_FLAG_ENABLED = 'Flag enabled successfully'
SUCCESS_FLAG_DISABLED = 'Flag disabled successfully'
SUCCESS_EXPERIMENT_STARTED = 'Experiment started successfully'
SUCCESS_EXPERIMENT_PAUSED = 'Experiment paused successfully'
SUCCESS_VARIANT_ASSIGNED = 'Variant assigned successfully'

# Validation messages
VALIDATION_FLAG_NAME_REQUIRED = 'Flag name is required'
VALIDATION_FLAG_NAME_TOO_LONG = f'Flag name must not exceed {MAX_FLAG_NAME_LENGTH} characters'
VALIDATION_ROLLOUT_PERCENTAGE_INVALID = 'Rollout percentage must be between 0 and 100'
VALIDATION_VARIANT_WEIGHT_INVALID = 'Variant weight must be between 0 and 100'
