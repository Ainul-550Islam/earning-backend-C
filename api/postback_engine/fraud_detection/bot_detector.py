"""
fraud_detection/bot_detector.py
────────────────────────────────
Detects bot/crawler traffic based on:
  - User-Agent string analysis (known bots, empty UA, suspicious patterns)
  - Request header anomalies (missing Accept, Accept-Language)
  - Behavioral patterns (too-fast click-to-conversion)
  - Device fingerprint analysis
"""
from __future__ import annotations
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Known bot user-agent fragments (lowercase)
_BOT_UA_PATTERNS = [
    r"googlebot", r"bingbot", r"slurp", r"duckduckbot", r"baiduspider",
    r"yandexbot", r"facebookexternalhit", r"twitterbot", r"ahrefsbot",
    r"mj12bot", r"semrushbot", r"rogerbot", r"screaming.frog",
    r"python-requests", r"curl/", r"wget/", r"libwww-perl",
    r"java/\d", r"okhttp", r"go-http-client", r"axios/",
    r"scrapy", r"phantomjs", r"headlesschrome", r"puppeteer",
    r"selenium", r"webdriver", r"slimerjs", r"casperjs",
    r"apachebench", r"httpie", r"insomnia",
]
_BOT_COMPILED = [re.compile(p, re.IGNORECASE) for p in _BOT_UA_PATTERNS]

# Suspicious but not definitive
_SUSPICIOUS_UA_PATTERNS = [
    r"^Mozilla/\d\.\d\s*$",        # empty generic UA
    r"bot", r"crawler", r"spider",
    r"scraper", r"fetch", r"scan",
]
_SUSPICIOUS_COMPILED = [re.compile(p, re.IGNORECASE) for p in _SUSPICIOUS_UA_PATTERNS]


class BotDetector:

    def check_user_agent(self, user_agent: str) -> Tuple[bool, float]:
        """
        Returns (is_bot, confidence_score 0-100).
        """
        if not user_agent or not user_agent.strip():
            return True, 90.0   # No UA = almost certainly a bot

        ua = user_agent.strip()

        # Known bot patterns → definitive
        for pattern in _BOT_COMPILED:
            if pattern.search(ua):
                return True, 95.0

        # Suspicious patterns → flag but not definitive
        for pattern in _SUSPICIOUS_COMPILED:
            if pattern.search(ua):
                return False, 55.0   # flag for review

        return False, 0.0

    def check_headers(self, headers: dict) -> Tuple[bool, float]:
        """
        Check request headers for bot indicators.
        Real browsers always send Accept, Accept-Language, etc.
        """
        score = 0.0
        h = {k.lower(): v for k, v in headers.items()}

        # Real browsers always send Accept
        if "accept" not in h:
            score += 30

        # Real browsers send Accept-Language
        if "accept-language" not in h:
            score += 20

        # Missing Accept-Encoding is suspicious
        if "accept-encoding" not in h:
            score += 15

        # Connection header present in real browsers
        if "connection" not in h:
            score += 10

        is_bot = score >= 60
        return is_bot, min(score, 100.0)

    def check_timing(self, click_to_conversion_seconds: int) -> Tuple[bool, float]:
        """
        Conversion in < 3 seconds = bot (impossible for a human to complete an offer).
        Conversion in < 30 seconds = very suspicious.
        """
        if click_to_conversion_seconds < 3:
            return True, 95.0
        if click_to_conversion_seconds < 30:
            return False, 50.0
        return False, 0.0


# Module-level singleton
bot_detector = BotDetector()
