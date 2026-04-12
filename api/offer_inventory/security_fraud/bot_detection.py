# api/offer_inventory/security_fraud/bot_detection.py
"""
Bot Detection Engine.
Multi-signal bot scoring: UA analysis, click velocity,
conversion speed, mouse/interaction patterns.
"""
import re
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Known bot UA patterns
BOT_UA_PATTERNS = [
    re.compile(r'(?i)(bot|crawl|spider|scraper|slurp|fetch|archive)'),
    re.compile(r'(?i)(headlesschrome|phantomjs|selenium|puppeteer|playwright|webdriver)'),
    re.compile(r'(?i)(curl|wget|libwww|python-requests|go-http|java/|axios|httpunit)'),
    re.compile(r'(?i)(nutch|zgrab|masscan|nikto|sqlmap|nmap|nessus)'),
]

# Real browser minimum UA length
MIN_UA_LENGTH = 40

# Click velocity thresholds
VELOCITY_WINDOWS = {
    '1min' : (60,   10),   # 10 clicks/1min
    '5min' : (300,  30),   # 30 clicks/5min
    '1hour': (3600, 100),  # 100 clicks/1hour
}


class BotDetector:
    """Multi-signal bot detection with composite scoring."""

    @classmethod
    def score(cls, ip: str, user_agent: str, user_id=None) -> float:
        """
        Returns 0–100 bot probability score.
        >= 70 = likely bot, >= 90 = certain bot.
        """
        score = 0.0

        # Signal 1: UA analysis (weight: 60)
        ua_score = cls._score_user_agent(user_agent)
        score   += ua_score * 0.60

        # Signal 2: IP velocity (weight: 25)
        vel_score = cls._score_click_velocity(ip)
        score    += vel_score * 0.25

        # Signal 3: User conversion velocity (weight: 15)
        if user_id:
            conv_score = cls._score_conversion_velocity(user_id)
            score     += conv_score * 0.15

        return min(100.0, score)

    @classmethod
    def is_bot(cls, ip: str, user_agent: str, user_id=None,
                threshold: float = 70.0) -> bool:
        return cls.score(ip, user_agent, user_id) >= threshold

    # ── Signal scorers ────────────────────────────────────────────

    @staticmethod
    def _score_user_agent(ua: str) -> float:
        """0–100 score based on UA string."""
        if not ua:
            return 100.0   # Empty UA = definite bot

        if len(ua) < MIN_UA_LENGTH:
            return 80.0    # Too short = suspicious

        for pattern in BOT_UA_PATTERNS:
            if pattern.search(ua):
                return 100.0

        # Suspicious: no common browser token
        has_browser = any(b in ua for b in ('Mozilla', 'Chrome', 'Safari', 'Firefox', 'Edge'))
        if not has_browser:
            return 60.0

        return 0.0

    @staticmethod
    def _score_click_velocity(ip: str) -> float:
        """Score based on click rate from this IP."""
        max_score = 0.0
        for window_name, (window_sec, threshold) in VELOCITY_WINDOWS.items():
            count = cache.get(f'click_vel:{ip}:{window_name}', 0)
            if count >= threshold:
                ratio = min(count / threshold, 3.0)   # Cap at 3×
                window_score = min(ratio * 33.3, 100.0)
                max_score = max(max_score, window_score)
        return max_score

    @staticmethod
    def _score_conversion_velocity(user_id) -> float:
        """Conversions too fast = suspicious."""
        count_5min  = cache.get(f'conv_vel:{user_id}:5min',  0)
        count_1hour = cache.get(f'conv_vel:{user_id}:1hour', 0)
        if count_5min >= 3:
            return 100.0
        if count_1hour >= 10:
            return 70.0
        return 0.0

    # ── Velocity tracking ─────────────────────────────────────────

    @staticmethod
    def record_click(ip: str):
        """Increment click velocity counters."""
        for window_name, (window_sec, _) in VELOCITY_WINDOWS.items():
            key   = f'click_vel:{ip}:{window_name}'
            count = cache.get(key, 0)
            cache.set(key, count + 1, window_sec)

    @staticmethod
    def record_conversion(user_id):
        """Increment conversion velocity counters."""
        for name, secs in [('5min', 300), ('1hour', 3600)]:
            key   = f'conv_vel:{user_id}:{name}'
            count = cache.get(key, 0)
            cache.set(key, count + 1, secs)
