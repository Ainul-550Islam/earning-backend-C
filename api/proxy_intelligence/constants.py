# Risk Score Thresholds
RISK_VERY_LOW_MAX = 20
RISK_LOW_MAX = 40
RISK_MEDIUM_MAX = 60
RISK_HIGH_MAX = 80
RISK_CRITICAL_MIN = 81

# Cache TTL (seconds)
IP_INTELLIGENCE_CACHE_TTL = 3600        # 1 hour
BLACKLIST_CACHE_TTL = 300               # 5 minutes
THREAT_FEED_CACHE_TTL = 7200           # 2 hours
GEO_CACHE_TTL = 86400                  # 24 hours

# Rate Limiting
MAX_REQUESTS_PER_MINUTE = 60
MAX_REQUESTS_PER_HOUR = 1000
VELOCITY_WINDOW_SECONDS = 60

# Detection Confidence Thresholds
VPN_CONFIDENCE_THRESHOLD = 0.75
PROXY_CONFIDENCE_THRESHOLD = 0.70
TOR_CONFIDENCE_THRESHOLD = 0.95
DATACENTER_CONFIDENCE_THRESHOLD = 0.80

# Known Datacenter ASN prefixes (partial list)
DATACENTER_ASN_PREFIXES = [
    'AS14061',  # DigitalOcean
    'AS16509',  # Amazon AWS
    'AS15169',  # Google Cloud
    'AS8075',   # Microsoft Azure
    'AS13335',  # Cloudflare
    'AS20940',  # Akamai
]

# Tor Project - Check URL
TOR_EXIT_NODE_LIST_URL = 'https://check.torproject.org/torbulkexitlist'

# Default ML Model version
DEFAULT_ML_MODEL_VERSION = '1.0.0'

# Max fingerprint age (days)
DEVICE_FINGERPRINT_MAX_AGE_DAYS = 90

# Anomaly detection window
ANOMALY_WINDOW_HOURS = 24

# Threat feed sources
THREAT_FEED_SOURCES = [
    'abuseipdb',
    'virustotal',
    'shodan',
    'alienvault',
    'crowdsec',
]

# API request log retention (days)
API_LOG_RETENTION_DAYS = 30
PERFORMANCE_METRIC_RETENTION_DAYS = 90
