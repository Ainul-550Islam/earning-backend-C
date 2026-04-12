import re
import logging
from ...constants import BOT_UA_PATTERNS

logger = logging.getLogger('smartlink.bot_detection')

# Known bot User-Agent patterns (compiled for speed)
BOT_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in BOT_UA_PATTERNS]

# Known search engine bots (allowed through but not tracked)
KNOWN_GOOD_BOTS = {
    'googlebot', 'bingbot', 'slurp', 'duckduckbot',
    'baiduspider', 'yandexbot', 'facebot',
}


class BotDetectionService:
    """
    Detect bots, crawlers, and automated traffic.
    Combines UA-pattern matching, IP-based checks, and behavioral signals.
    """

    def detect(self, ip: str, user_agent: str) -> tuple:
        """
        Detect if the request is from a bot.

        Returns:
            (is_bot: bool, bot_type: str)
        """
        if not user_agent:
            return True, 'empty_ua'

        ua_lower = user_agent.lower()

        # Check known good bots (search engines)
        for bot_name in KNOWN_GOOD_BOTS:
            if bot_name in ua_lower:
                return True, f'search_engine:{bot_name}'

        # Check bad bot patterns
        for pattern in BOT_PATTERNS_COMPILED:
            if pattern.search(user_agent):
                return True, f'ua_pattern:{pattern.pattern}'

        # Headless browser detection
        headless_signs = [
            'headlesschrome', 'phantomjs', 'selenium',
            'webdriver', 'puppeteer', 'playwright',
        ]
        for sign in headless_signs:
            if sign in ua_lower:
                return True, f'headless:{sign}'

        # Suspicious UA: too short or too long
        if len(user_agent) < 20 or len(user_agent) > 1000:
            return True, 'suspicious_ua_length'

        # No mobile/desktop signatures in UA
        has_browser_sig = any(b in ua_lower for b in [
            'mozilla', 'webkit', 'gecko', 'trident', 'chrome', 'safari'
        ])
        if not has_browser_sig:
            return True, 'no_browser_signature'

        return False, ''

    def detect_from_behavior(self, click_interval_ms: float, session_click_count: int) -> bool:
        """
        Behavioral bot detection: clicks too fast or too many in session.

        Args:
            click_interval_ms: milliseconds since last click from this session
            session_click_count: total clicks in this session

        Returns:
            True if behavior looks bot-like
        """
        # Humans can't click faster than ~200ms consistently
        if click_interval_ms < 100 and session_click_count > 5:
            return True

        # Extremely high click count in one session
        if session_click_count > 100:
            return True

        return False

    def get_bot_type(self, user_agent: str) -> str:
        """Get a human-readable bot type from user agent."""
        ua_lower = user_agent.lower()

        for bot_name in KNOWN_GOOD_BOTS:
            if bot_name in ua_lower:
                return bot_name

        for p in ['curl', 'wget', 'python', 'java', 'go-http']:
            if p in ua_lower:
                return f'http_client:{p}'

        for p in ['selenium', 'puppeteer', 'playwright', 'phantomjs']:
            if p in ua_lower:
                return f'automation:{p}'

        return 'unknown_bot'
