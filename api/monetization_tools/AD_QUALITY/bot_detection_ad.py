"""AD_QUALITY/bot_detection_ad.py — Bot/non-human traffic detection."""
import hashlib
from django.core.cache import cache


KNOWN_BOT_STRINGS = [
    "googlebot", "bingbot", "slurp", "duckduckbot", "baiduspider",
    "yandexbot", "facebot", "ia_archiver", "python-requests",
    "python-urllib", "java/", "curl/", "wget/",
]

HEADLESS_BROWSER_STRINGS = [
    "phantomjs", "headlesschrome", "selenium",
    "webdriver", "htmlunit", "puppeteer",
]


class BotDetector:
    @classmethod
    def is_bot(cls, user_agent: str) -> bool:
        ua = (user_agent or "").lower()
        return (any(b in ua for b in KNOWN_BOT_STRINGS) or
                any(h in ua for h in HEADLESS_BROWSER_STRINGS))

    @classmethod
    def is_headless(cls, user_agent: str) -> bool:
        ua = (user_agent or "").lower()
        return any(h in ua for h in HEADLESS_BROWSER_STRINGS)

    @classmethod
    def generate_challenge_token(cls, session_id: str, secret: str = "") -> str:
        data = f"{session_id}{secret}".encode()
        return hashlib.sha256(data).hexdigest()[:16]

    @classmethod
    def verify_challenge(cls, session_id: str, token: str, secret: str = "") -> bool:
        expected = cls.generate_challenge_token(session_id, secret)
        return expected == token

    @classmethod
    def rate_check(cls, fingerprint: str, max_per_min: int = 20) -> bool:
        key   = f"mt:bot_rate:{fingerprint}"
        count = int(cache.get(key, 0))
        if count >= max_per_min:
            return False
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, 60)
        return True
