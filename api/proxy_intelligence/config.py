"""
Proxy Intelligence Configuration  (PRODUCTION-READY — COMPLETE)
=================================================================
Central configuration loader for the proxy_intelligence module.
Reads from Django settings (PROXY_INTELLIGENCE dict) with
sensible production defaults for every setting.

Access in code:
    from api.proxy_intelligence.config import PIConfig
    if PIConfig.BLOCK_TOR:
        ...

All settings can be overridden in settings.py:
    PROXY_INTELLIGENCE = {
        'BLOCK_TOR': True,
        'BLOCK_VPN': False,
        ...
    }
"""
from django.conf import settings


def _pi(key: str, default):
    """Read a value from settings.PROXY_INTELLIGENCE dict."""
    return getattr(settings, 'PROXY_INTELLIGENCE', {}).get(key, default)


class PIConfig:
    """
    Centralised configuration for the Proxy Intelligence module.
    All values are lazily read from Django settings at access time,
    so they respect Django's settings override in tests.
    """

    # ── Detection Thresholds ──────────────────────────────────────────────

    @classmethod
    def vpn_confidence_threshold(cls) -> float:
        """Minimum VPN detection confidence score (0.0–1.0) to flag as VPN."""
        return _pi('VPN_CONFIDENCE_THRESHOLD', 0.55)

    @classmethod
    def proxy_confidence_threshold(cls) -> float:
        """Minimum proxy detection confidence score to flag as proxy."""
        return _pi('PROXY_CONFIDENCE_THRESHOLD', 0.50)

    @classmethod
    def tor_confidence_threshold(cls) -> float:
        """Minimum Tor detection confidence to flag (usually 1.0 — list-based)."""
        return _pi('TOR_CONFIDENCE_THRESHOLD', 0.90)

    @classmethod
    def datacenter_confidence_threshold(cls) -> float:
        """Minimum datacenter detection confidence."""
        return _pi('DATACENTER_CONFIDENCE_THRESHOLD', 0.40)

    # ── Risk Score Thresholds ─────────────────────────────────────────────

    @classmethod
    def risk_score_low(cls) -> int:
        """Risk score ceiling for LOW level."""
        return _pi('RISK_SCORE_LOW', 40)

    @classmethod
    def risk_score_medium(cls) -> int:
        """Risk score ceiling for MEDIUM level."""
        return _pi('RISK_SCORE_MEDIUM', 60)

    @classmethod
    def risk_score_high(cls) -> int:
        """Risk score ceiling for HIGH level."""
        return _pi('RISK_SCORE_HIGH', 80)

    # ── Blocking Behaviour ────────────────────────────────────────────────

    @classmethod
    def block_tor(cls) -> bool:
        """Block all Tor exit node traffic. Default: True."""
        return _pi('BLOCK_TOR', True)

    @classmethod
    def block_vpn(cls) -> bool:
        """Block all VPN traffic. Default: False (use challenge instead)."""
        return _pi('BLOCK_VPN', False)

    @classmethod
    def block_proxy(cls) -> bool:
        """Block all proxy traffic. Default: False."""
        return _pi('BLOCK_PROXY', False)

    @classmethod
    def block_datacenter(cls) -> bool:
        """Block all datacenter traffic. Default: False."""
        return _pi('BLOCK_DATACENTER', False)

    @classmethod
    def challenge_vpn(cls) -> bool:
        """Challenge (CAPTCHA/2FA) VPN users instead of blocking. Default: True."""
        return _pi('CHALLENGE_VPN', True)

    @classmethod
    def challenge_proxy(cls) -> bool:
        """Challenge proxy users. Default: True."""
        return _pi('CHALLENGE_PROXY', True)

    # ── Velocity / Rate Limiting ──────────────────────────────────────────

    @classmethod
    def velocity_window_seconds(cls) -> int:
        """Default sliding window for velocity checks (seconds)."""
        return _pi('VELOCITY_WINDOW_SECONDS', 60)

    @classmethod
    def max_requests_per_minute(cls) -> int:
        """Default maximum requests per minute before rate limiting."""
        return _pi('MAX_REQUESTS_PER_MINUTE', 120)

    @classmethod
    def max_login_attempts(cls) -> int:
        """Max login attempts per minute before blocking."""
        return _pi('MAX_LOGIN_ATTEMPTS', 5)

    @classmethod
    def max_offer_completions(cls) -> int:
        """Max offer completions per 5 minutes."""
        return _pi('MAX_OFFER_COMPLETIONS', 10)

    @classmethod
    def max_referral_signups(cls) -> int:
        """Max referral signups per hour from same IP."""
        return _pi('MAX_REFERRAL_SIGNUPS', 3)

    # ── Cache TTL Settings ────────────────────────────────────────────────

    @classmethod
    def cache_intelligence_ttl(cls) -> int:
        """TTL for IPIntelligence cache entries (seconds). Default: 1 hour."""
        return _pi('CACHE_INTELLIGENCE_TTL', 3600)

    @classmethod
    def cache_blacklist_ttl(cls) -> int:
        """TTL for blacklist status cache (seconds). Default: 5 minutes."""
        return _pi('CACHE_BLACKLIST_TTL', 300)

    @classmethod
    def cache_whitelist_ttl(cls) -> int:
        """TTL for whitelist status cache (seconds). Default: 5 minutes."""
        return _pi('CACHE_WHITELIST_TTL', 300)

    @classmethod
    def cache_geo_ttl(cls) -> int:
        """TTL for geolocation cache (seconds). Default: 24 hours."""
        return _pi('CACHE_GEO_TTL', 86400)

    @classmethod
    def cache_threat_feed_ttl(cls) -> int:
        """TTL for threat feed API results (seconds). Default: 4 hours."""
        return _pi('CACHE_THREAT_FEED_TTL', 14400)

    # ── Data Retention ────────────────────────────────────────────────────

    @classmethod
    def api_log_retention_days(cls) -> int:
        """Days to keep APIRequestLog records before cleanup. Default: 30."""
        return _pi('API_LOG_RETENTION_DAYS', 30)

    @classmethod
    def performance_metric_retention_days(cls) -> int:
        """Days to keep PerformanceMetric records. Default: 90."""
        return _pi('PERFORMANCE_METRIC_RETENTION_DAYS', 90)

    @classmethod
    def velocity_metric_retention_days(cls) -> int:
        """Days to keep VelocityMetric records. Default: 7."""
        return _pi('VELOCITY_METRIC_RETENTION_DAYS', 7)

    @classmethod
    def fraud_attempt_retention_days(cls) -> int:
        """Days to keep resolved FraudAttempt records. Default: 365."""
        return _pi('FRAUD_ATTEMPT_RETENTION_DAYS', 365)

    # ── Feature Flags ─────────────────────────────────────────────────────

    @classmethod
    def log_all_requests(cls) -> bool:
        """Log every API request to APIRequestLog. Default: True."""
        return _pi('LOG_ALL_REQUESTS', True)

    @classmethod
    def enable_ml_scoring(cls) -> bool:
        """Enable ML-based fraud scoring. Default: True (falls back if no model)."""
        return _pi('ENABLE_ML_SCORING', True)

    @classmethod
    def enable_threat_feeds(cls) -> bool:
        """Enable third-party threat feed checks (AbuseIPDB, IPQS, etc). Default: True."""
        return _pi('ENABLE_THREAT_FEEDS', True)

    @classmethod
    def enable_port_scanning(cls) -> bool:
        """Enable port scanning during VPN/proxy detection. Default: True."""
        return _pi('ENABLE_PORT_SCANNING', True)

    @classmethod
    def enable_whois_lookup(cls) -> bool:
        """Enable WHOIS lookups for IP organization data. Default: False (slow)."""
        return _pi('ENABLE_WHOIS_LOOKUP', False)

    @classmethod
    def enable_real_time_alerts(cls) -> bool:
        """Enable real-time webhook/WebSocket alerts. Default: True."""
        return _pi('ENABLE_REAL_TIME_ALERTS', True)

    @classmethod
    def skip_private_ips(cls) -> bool:
        """Skip all checks for RFC1918 private IP addresses. Default: True."""
        return _pi('SKIP_PRIVATE_IPS', True)

    @classmethod
    def min_risk_score_to_log(cls) -> int:
        """Minimum risk score before saving a VPNDetectionLog. Default: 0 (log all)."""
        return _pi('MIN_RISK_SCORE_TO_LOG', 0)

    # ── External API Settings ─────────────────────────────────────────────

    @classmethod
    def abuseipdb_enabled(cls) -> bool:
        """Enable AbuseIPDB integration. Default: True."""
        return _pi('ABUSEIPDB_ENABLED', True)

    @classmethod
    def abuseipdb_max_age_days(cls) -> int:
        """Only count reports newer than this many days."""
        return _pi('ABUSEIPDB_MAX_AGE_DAYS', 90)

    @classmethod
    def ipqs_enabled(cls) -> bool:
        """Enable IPQualityScore integration. Default: True."""
        return _pi('IPQS_ENABLED', True)

    @classmethod
    def ipqs_strict_mode(cls) -> bool:
        """Use strict mode for IPQS checks (higher sensitivity). Default: False."""
        return _pi('IPQS_STRICT_MODE', False)

    @classmethod
    def maxmind_enabled(cls) -> bool:
        """Enable MaxMind GeoIP2 integration. Default: True."""
        return _pi('MAXMIND_ENABLED', True)

    @classmethod
    def virustotal_enabled(cls) -> bool:
        """Enable VirusTotal integration. Default: False (strict rate limits)."""
        return _pi('VIRUSTOTAL_ENABLED', False)

    @classmethod
    def shodan_enabled(cls) -> bool:
        """Enable Shodan integration. Default: False."""
        return _pi('SHODAN_ENABLED', False)

    # ── Tor Node Sync ─────────────────────────────────────────────────────

    @classmethod
    def tor_exit_node_list_url(cls) -> str:
        """URL to download the Tor Project exit node list."""
        return _pi(
            'TOR_EXIT_NODE_LIST_URL',
            'https://check.torproject.org/torbulkexitlist'
        )

    @classmethod
    def tor_sync_interval_hours(cls) -> int:
        """How often to sync the Tor exit node list (hours). Default: 6."""
        return _pi('TOR_SYNC_INTERVAL_HOURS', 6)

    # ── Alert Settings ────────────────────────────────────────────────────

    @classmethod
    def alert_threshold_score(cls) -> int:
        """Default minimum risk score to trigger alerts. Default: 80."""
        return _pi('ALERT_THRESHOLD_SCORE', 80)

    @classmethod
    def admin_emails(cls) -> list:
        """List of admin email addresses for daily summaries."""
        return _pi('ADMIN_EMAILS', [])

    @classmethod
    def default_webhook_url(cls) -> str:
        """Default webhook URL for high-risk IP alerts."""
        return _pi('DEFAULT_WEBHOOK_URL', '')

    # ── ML Model Settings ─────────────────────────────────────────────────

    @classmethod
    def ml_model_path(cls) -> str:
        """Path to the trained fraud detection ML model file."""
        return _pi('ML_MODEL_PATH', '/tmp/pi_fraud_model.pkl')

    @classmethod
    def ml_anomaly_model_path(cls) -> str:
        """Path to the anomaly detection model file."""
        return _pi('ML_ANOMALY_MODEL_PATH', '/tmp/pi_anomaly_model.pkl')

    @classmethod
    def ml_fraud_threshold(cls) -> float:
        """Minimum ML fraud probability to flag (0.0–1.0). Default: 0.50."""
        return _pi('ML_FRAUD_THRESHOLD', 0.50)

    # ── Multi-Account Detection ───────────────────────────────────────────

    @classmethod
    def max_accounts_per_ip(cls) -> int:
        """Max accounts allowed from same IP before flagging. Default: 3."""
        return _pi('MAX_ACCOUNTS_PER_IP', 3)

    @classmethod
    def max_accounts_per_device(cls) -> int:
        """Max accounts allowed per device fingerprint. Default: 2."""
        return _pi('MAX_ACCOUNTS_PER_DEVICE', 2)

    @classmethod
    def multi_account_window_days(cls) -> int:
        """Days to look back when checking multi-account links. Default: 30."""
        return _pi('MULTI_ACCOUNT_WINDOW_DAYS', 30)

    # ── Blacklist Defaults ────────────────────────────────────────────────

    @classmethod
    def default_blacklist_hours(cls) -> int:
        """Default TTL for temporary blacklist entries (hours). Default: 72."""
        return _pi('DEFAULT_BLACKLIST_HOURS', 72)

    @classmethod
    def auto_blacklist_on_fraud(cls) -> bool:
        """Auto-blacklist IPs when fraud is confirmed. Default: True."""
        return _pi('AUTO_BLACKLIST_ON_FRAUD', True)

    @classmethod
    def auto_blacklist_threshold(cls) -> int:
        """Risk score threshold for auto-blacklisting. Default: 90."""
        return _pi('AUTO_BLACKLIST_THRESHOLD', 90)

    # ── Full settings dump (for debugging) ────────────────────────────────

    @classmethod
    def all_settings(cls) -> dict:
        """Return all PI config values as a dict (for admin/debug endpoint)."""
        return {
            'VPN_CONFIDENCE_THRESHOLD':        cls.vpn_confidence_threshold(),
            'PROXY_CONFIDENCE_THRESHOLD':      cls.proxy_confidence_threshold(),
            'TOR_CONFIDENCE_THRESHOLD':        cls.tor_confidence_threshold(),
            'DATACENTER_CONFIDENCE_THRESHOLD': cls.datacenter_confidence_threshold(),
            'BLOCK_TOR':                       cls.block_tor(),
            'BLOCK_VPN':                       cls.block_vpn(),
            'BLOCK_PROXY':                     cls.block_proxy(),
            'BLOCK_DATACENTER':                cls.block_datacenter(),
            'CHALLENGE_VPN':                   cls.challenge_vpn(),
            'CHALLENGE_PROXY':                 cls.challenge_proxy(),
            'VELOCITY_WINDOW_SECONDS':         cls.velocity_window_seconds(),
            'MAX_REQUESTS_PER_MINUTE':         cls.max_requests_per_minute(),
            'CACHE_INTELLIGENCE_TTL':          cls.cache_intelligence_ttl(),
            'CACHE_BLACKLIST_TTL':             cls.cache_blacklist_ttl(),
            'LOG_ALL_REQUESTS':                cls.log_all_requests(),
            'ENABLE_ML_SCORING':               cls.enable_ml_scoring(),
            'ENABLE_THREAT_FEEDS':             cls.enable_threat_feeds(),
            'ENABLE_PORT_SCANNING':            cls.enable_port_scanning(),
            'SKIP_PRIVATE_IPS':                cls.skip_private_ips(),
            'ABUSEIPDB_ENABLED':               cls.abuseipdb_enabled(),
            'IPQS_ENABLED':                    cls.ipqs_enabled(),
            'MAXMIND_ENABLED':                 cls.maxmind_enabled(),
            'VIRUSTOTAL_ENABLED':              cls.virustotal_enabled(),
            'ALERT_THRESHOLD_SCORE':           cls.alert_threshold_score(),
            'MAX_ACCOUNTS_PER_IP':             cls.max_accounts_per_ip(),
            'DEFAULT_BLACKLIST_HOURS':         cls.default_blacklist_hours(),
            'AUTO_BLACKLIST_ON_FRAUD':         cls.auto_blacklist_on_fraud(),
            'AUTO_BLACKLIST_THRESHOLD':        cls.auto_blacklist_threshold(),
        }
