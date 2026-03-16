# =============================================================================
# auto_mod/constants.py
# =============================================================================
"""
All magic numbers, string keys, and configuration constants for auto_mod.
Never import Django settings here — use settings only in apps.py or services.
"""

from decimal import Decimal

# ---------------------------------------------------------------------------
# Confidence / Score thresholds
# ---------------------------------------------------------------------------
CONFIDENCE_MIN: float = 0.0
CONFIDENCE_MAX: float = 1.0

# Auto-approve when AI confidence ≥ this value
AUTO_APPROVE_THRESHOLD: float = 0.90

# Auto-reject when AI confidence of REJECTION ≥ this value
AUTO_REJECT_THRESHOLD: float = 0.85

# Send to human review when confidence falls between thresholds
HUMAN_REVIEW_LOWER: float = 0.50
HUMAN_REVIEW_UPPER: float = 0.89

# Risk score bands
RISK_SCORE_LOW: float    = 0.30
RISK_SCORE_MEDIUM: float = 0.60
RISK_SCORE_HIGH: float   = 0.80

# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------
MAX_RULES_PER_EVALUATION: int   = 50
MAX_CONDITIONS_PER_RULE: int    = 20
RULE_PRIORITY_MIN: int          = 1
RULE_PRIORITY_MAX: int          = 100

# ---------------------------------------------------------------------------
# Proof / Image scanning
# ---------------------------------------------------------------------------
MAX_PROOF_FILE_SIZE_MB: int     = 20
MAX_PROOF_FILES_PER_SUBMISSION: int = 10
SUPPORTED_IMAGE_FORMATS: tuple  = ("jpg", "jpeg", "png", "gif", "webp", "bmp")
SUPPORTED_DOC_FORMATS: tuple    = ("pdf", "txt", "docx")
OCR_CONFIDENCE_MIN: float       = 0.70    # discard OCR results below this
IMAGE_SCAN_TIMEOUT_SEC: int     = 30
MAX_IMAGE_DIMENSION_PX: int     = 8_192

# ---------------------------------------------------------------------------
# TaskBot
# ---------------------------------------------------------------------------
MAX_BOT_RETRIES: int            = 3
BOT_RETRY_DELAY_SEC: int        = 60
MAX_CONCURRENT_BOT_TASKS: int   = 10
BOT_HEARTBEAT_INTERVAL_SEC: int = 30
BOT_TASK_TIMEOUT_SEC: int       = 300     # 5 min

# ---------------------------------------------------------------------------
# Suspicious submission
# ---------------------------------------------------------------------------
MAX_SUBMISSION_TEXT_LENGTH: int = 10_000
SUSPICIOUS_KEYWORD_LIMIT: int   = 100     # max keywords in a single rule
FLAG_AUTO_ESCALATE_SCORE: float = 0.75    # auto-escalate above this risk
SUBMISSION_EXPIRY_DAYS: int     = 90

# ---------------------------------------------------------------------------
# ML model paths / identifiers
# ---------------------------------------------------------------------------
ML_IMAGE_MODEL_NAME: str       = "auto_mod_image_v1"
ML_TEXT_MODEL_NAME: str        = "auto_mod_text_v1"
ML_MODEL_REGISTRY_PATH: str    = "ml_models/"
ML_TRAINING_BATCH_SIZE: int    = 32
ML_MAX_TEXT_TOKENS: int        = 512

# ---------------------------------------------------------------------------
# Celery task names
# ---------------------------------------------------------------------------
TASK_SCAN_SUBMISSION: str       = "auto_mod.tasks.scan_submission"
TASK_EVALUATE_RULES: str        = "auto_mod.tasks.evaluate_rules"
TASK_RUN_IMAGE_SCAN: str        = "auto_mod.tasks.run_image_scan"
TASK_RUN_TEXT_ANALYSIS: str     = "auto_mod.tasks.run_text_analysis"
TASK_BOT_PROCESS: str           = "auto_mod.tasks.bot_process_task"
TASK_RETRAIN_MODEL: str         = "auto_mod.tasks.retrain_model"
TASK_CLEANUP_OLD_SUBMISSIONS: str = "auto_mod.tasks.cleanup_old_submissions"

# ---------------------------------------------------------------------------
# Cache keys & TTLs
# ---------------------------------------------------------------------------
CACHE_KEY_ACTIVE_RULES: str     = "auto_mod:rules:active:{submission_type}"
CACHE_KEY_SCAN_RESULT: str      = "auto_mod:scan:{submission_id}"
CACHE_KEY_BOT_STATUS: str       = "auto_mod:bot:status:{bot_id}"
CACHE_KEY_MODEL_VERSION: str    = "auto_mod:ml:version:{model_name}"

CACHE_TTL_RULES: int            = 300      # 5 min
CACHE_TTL_SCAN_RESULT: int      = 3_600    # 1 hour
CACHE_TTL_BOT_STATUS: int       = 60       # 1 min
CACHE_TTL_MODEL_VERSION: int    = 86_400   # 24 h

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE: int  = 20
MAX_PAGE_SIZE: int      = 200
