# config/settings/cms_additions.py
import os

_CMS_APPS = [
    "cms",
    "offerwall",
    "api_finance",
    "storages",
    "imagekit",
    "django_elasticsearch_dsl",
    "rosetta",
]
INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in _CMS_APPS] + _CMS_APPS  # noqa: F821

_CMS_MIDDLEWARE = [
    "cms.middleware.MaintenanceModeMiddleware",
    "cms.middleware.CMSRequestTimingMiddleware",
    "cms.middleware.CMSSiteConfigMiddleware",
    "cms.middleware.CMSSecurityHeadersMiddleware",
    "cms.middleware.WebSocketAuthMiddleware",
    "cms.middleware.AnalyticsTrackingMiddleware",
    "cms.middleware.SurveyRateLimitMiddleware",
    "cms.middleware.TaskSecurityMiddleware",
    "cms.middleware.RewardSecurityMiddleware",
]
for _mw in _CMS_MIDDLEWARE:
    if _mw not in MIDDLEWARE:  # noqa: F821
        MIDDLEWARE.append(_mw)  # noqa: F821

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({  # noqa: F821
    "cms_write":        "60/minute",
    "cpalead_postback": "500/day",
    "cms_withdrawal":   "5/hour",
    "cms_quiz":         "30/hour",
    "cms_form_submit":  "20/hour",
})

_cms_beat = {}
try:
    from api.cms.celery_beat_config import CMS_BEAT_SCHEDULE as _s
    _cms_beat.update(_s)
except ImportError:
    pass
if _cms_beat:
    CELERY_BEAT_SCHEDULE.update(_cms_beat)  # noqa: F821

LOGGING["loggers"].update({  # noqa: F821
    "cms": {"handlers": ["console"], "level": "INFO", "propagate": False},
    "cms.integration": {"handlers": ["console"], "level": "INFO", "propagate": False},
    "cms.exceptions": {"handlers": ["console"], "level": "ERROR", "propagate": True},
    "offerwall": {"handlers": ["console"], "level": "INFO", "propagate": False},
    "api_finance": {"handlers": ["console"], "level": "INFO", "propagate": False},
})

ELASTICSEARCH_URL     = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
ELASTICSEARCH_ENABLED = os.environ.get("ELASTICSEARCH_ENABLED", "False") == "True"
ELASTICSEARCH_DSL = {"default": {"hosts": ELASTICSEARCH_URL}}

FCM_SERVER_KEY  = os.environ.get("FCM_SERVER_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = os.environ.get("VAPID_PUBLIC_KEY", "")

_USE_S3 = os.environ.get("USE_S3", "False") == "True"
if _USE_S3:
    DEFAULT_FILE_STORAGE    = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_ACCESS_KEY_ID       = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY   = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME", "cms-media")
    AWS_S3_REGION_NAME      = os.environ.get("AWS_REGION", "ap-southeast-1")
    AWS_S3_FILE_OVERWRITE   = False
    AWS_DEFAULT_ACL         = "private"

PAYPAL_CLIENT_ID     = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_SANDBOX       = os.environ.get("PAYPAL_SANDBOX", "True") == "True"

COINPAYMENTS_PUBLIC_KEY  = os.environ.get("COINPAYMENTS_PUBLIC_KEY", "")
COINPAYMENTS_PRIVATE_KEY = os.environ.get("COINPAYMENTS_PRIVATE_KEY", "")
BINANCE_PAY_API_KEY      = os.environ.get("BINANCE_PAY_API_KEY", "")
BINANCE_PAY_SECRET_KEY   = os.environ.get("BINANCE_PAY_SECRET_KEY", "")

CMS_OUTBOUND_WEBHOOKS = {
    "reward_earned":     [],
    "withdrawal":        [],
    "postback_approved": [],
    "survey_completed":  [],
}

METRICS_ENABLED   = True
SEND_ERROR_ALERTS = True

CACHES["version_control"] = {  # noqa: F821
    "BACKEND": "django_redis.cache.RedisCache",
    "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/3"),
    "TIMEOUT": 300,
    "KEY_PREFIX": "vc",
    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
}
