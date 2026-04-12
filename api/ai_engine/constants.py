"""
api/ai_engine/constants.py
===========================
AI Engine — সকল Constants।
"""

# ── Model Defaults ─────────────────────────────────────────────
DEFAULT_EMBEDDING_DIM       = 128
DEFAULT_ANOMALY_THRESHOLD   = 0.80
DEFAULT_CHURN_THRESHOLD     = 0.65
DEFAULT_FRAUD_THRESHOLD     = 0.75
DEFAULT_SPAM_THRESHOLD      = 0.70
DEFAULT_NSFW_THRESHOLD      = 0.85
DEFAULT_DRIFT_THRESHOLD     = 0.20
DEFAULT_CONFIDENCE_MIN      = 0.50

# ── Cache TTLs (seconds) ───────────────────────────────────────
CACHE_TTL_RECOMMENDATION    = 300       # 5 min
CACHE_TTL_USER_EMBEDDING    = 3600      # 1 hour
CACHE_TTL_SEGMENT           = 86400     # 1 day
CACHE_TTL_MODEL_META        = 600       # 10 min
CACHE_TTL_PREDICTION        = 60        # 1 min
CACHE_TTL_INSIGHT           = 1800      # 30 min

# ── Recommendation ─────────────────────────────────────────────
MAX_RECOMMENDATIONS         = 20
DEFAULT_RECOMMENDATIONS     = 10
MIN_INTERACTIONS_FOR_CF     = 5         # Collaborative Filtering minimum

# ── Batch Sizes ────────────────────────────────────────────────
BATCH_SIZE_TRAINING         = 1024
BATCH_SIZE_INFERENCE        = 256
BATCH_SIZE_EMBEDDING_UPDATE = 512
BATCH_SIZE_EXPORT           = 5000

# ── A/B Testing ────────────────────────────────────────────────
AB_TEST_MIN_SAMPLE_SIZE     = 1000
AB_TEST_DEFAULT_CONFIDENCE  = 0.95
AB_TEST_DEFAULT_DURATION_DAYS = 14

# ── NLP ────────────────────────────────────────────────────────
MAX_TEXT_LENGTH             = 5000
MIN_TEXT_LENGTH             = 3
SUPPORTED_LANGUAGES         = ['en', 'bn', 'hi', 'ar', 'ur']

# ── CV / Image ─────────────────────────────────────────────────
MAX_IMAGE_SIZE_MB           = 10
SUPPORTED_IMAGE_FORMATS     = ['jpg', 'jpeg', 'png', 'webp']
OCR_MIN_CONFIDENCE          = 0.70

# ── Anomaly Detection ─────────────────────────────────────────
ANOMALY_WINDOW_HOURS        = 24
MAX_ANOMALIES_PER_USER_DAY  = 10

# ── Feature Engineering ───────────────────────────────────────
FEATURE_FRESHNESS_HOURS     = 24        # Features stale after 24h
MAX_FEATURE_DIMENSIONS      = 512

# ── Model Performance Thresholds ──────────────────────────────
MIN_ACCEPTABLE_F1           = 0.70
MIN_ACCEPTABLE_AUC          = 0.75
MAX_ACCEPTABLE_RMSE         = 0.30
MAX_INFERENCE_LATENCY_MS    = 200

# ── Prediction Types ──────────────────────────────────────────
PREDICTION_TYPES = [
    'fraud', 'churn', 'ltv', 'conversion',
    'recommendation', 'click', 'revenue', 'anomaly',
    'sentiment', 'custom',
]

# ── Churn Risk Buckets ────────────────────────────────────────
CHURN_RISK_BUCKETS = {
    'very_low':  (0.00, 0.20),
    'low':       (0.20, 0.40),
    'medium':    (0.40, 0.60),
    'high':      (0.60, 0.80),
    'very_high': (0.80, 1.00),
}

# ── LTV Segments ──────────────────────────────────────────────
LTV_SEGMENTS = {
    'low':     (0,    500),
    'medium':  (500,  2000),
    'high':    (2000, 10000),
    'premium': (10000, float('inf')),
}

# ── Model Registry Keys ───────────────────────────────────────
MODEL_KEYS = {
    'fraud_detector':       'fraud_detection_v1',
    'churn_predictor':      'churn_prediction_v1',
    'ltv_predictor':        'ltv_prediction_v1',
    'offer_recommender':    'offer_recommendation_v1',
    'user_segmenter':       'user_segmentation_v1',
    'sentiment_analyzer':   'sentiment_analysis_v1',
    'anomaly_detector':     'anomaly_detection_v1',
}
