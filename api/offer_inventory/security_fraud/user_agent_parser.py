# api/offer_inventory/security_fraud/user_agent_parser.py
"""
User Agent Parser & Risk Analyzer.
Extracts device/browser/OS info and flags suspicious UAs.
"""
import re
import logging
from dataclasses import dataclass
from django.core.cache import cache

logger = logging.getLogger(__name__)


@dataclass
class ParsedUA:
    browser : str = 'Unknown'
    browser_version: str = ''
    os      : str = 'Unknown'
    os_version: str = ''
    device  : str = 'desktop'   # mobile | tablet | desktop | bot
    is_bot  : bool = False
    is_mobile: bool = False
    risk_score: float = 0.0
    raw     : str = ''


class UserAgentParser:
    """
    Lightweight UA parser without external dependency.
    Falls back to user-agents library if installed.
    """

    # ── Regex patterns ────────────────────────────────────────────
    MOBILE_RE  = re.compile(r'(?i)(android|iphone|ipod|blackberry|windows phone|opera mini)')
    TABLET_RE  = re.compile(r'(?i)(ipad|android.*tablet|kindle|silk)')
    CHROME_RE  = re.compile(r'Chrome/([\d.]+)')
    FIREFOX_RE = re.compile(r'Firefox/([\d.]+)')
    SAFARI_RE  = re.compile(r'Safari/([\d.]+)')
    EDGE_RE    = re.compile(r'Edg/([\d.]+)')
    WIN_RE     = re.compile(r'Windows NT ([\d.]+)')
    MAC_RE     = re.compile(r'Mac OS X ([\d_.]+)')
    ANDROID_RE = re.compile(r'Android ([\d.]+)')
    IOS_RE     = re.compile(r'(?:iPhone|iPad).*OS ([\d_]+)')

    @classmethod
    def parse(cls, ua_string: str) -> ParsedUA:
        """Parse UA string into structured data."""
        if not ua_string:
            return ParsedUA(is_bot=True, risk_score=100.0, raw=ua_string)

        # Try user-agents lib first
        try:
            from user_agents import parse as ua_parse
            ua = ua_parse(ua_string)
            result = ParsedUA(
                browser        = ua.browser.family,
                browser_version= str(ua.browser.version_string),
                os             = ua.os.family,
                os_version     = str(ua.os.version_string),
                device         = ('mobile' if ua.is_mobile else
                                  'tablet' if ua.is_tablet else
                                  'bot'    if ua.is_bot    else 'desktop'),
                is_bot         = ua.is_bot,
                is_mobile      = ua.is_mobile,
                raw            = ua_string,
            )
            result.risk_score = cls._risk_score(ua_string, result.is_bot)
            return result
        except ImportError:
            pass

        # Fallback: regex-based parsing
        result          = ParsedUA(raw=ua_string)
        result.is_bot   = bool(re.search(r'(?i)bot|crawl|spider|headless', ua_string))
        result.is_mobile= bool(cls.MOBILE_RE.search(ua_string))
        result.device   = ('bot'    if result.is_bot    else
                           'tablet' if cls.TABLET_RE.search(ua_string) else
                           'mobile' if result.is_mobile else 'desktop')

        m = cls.CHROME_RE.search(ua_string)
        if m:
            result.browser = 'Chrome'; result.browser_version = m.group(1)
        elif cls.FIREFOX_RE.search(ua_string):
            m = cls.FIREFOX_RE.search(ua_string)
            result.browser = 'Firefox'; result.browser_version = m.group(1) if m else ''
        elif cls.EDGE_RE.search(ua_string):
            result.browser = 'Edge'
        elif cls.SAFARI_RE.search(ua_string):
            result.browser = 'Safari'

        m = cls.WIN_RE.search(ua_string)
        if m:
            result.os = 'Windows'; result.os_version = m.group(1)
        elif cls.MAC_RE.search(ua_string):
            result.os = 'macOS'
        elif cls.ANDROID_RE.search(ua_string):
            m = cls.ANDROID_RE.search(ua_string)
            result.os = 'Android'; result.os_version = m.group(1) if m else ''
        elif cls.IOS_RE.search(ua_string):
            result.os = 'iOS'

        result.risk_score = cls._risk_score(ua_string, result.is_bot)
        return result

    @staticmethod
    def _risk_score(ua: str, is_bot: bool) -> float:
        if is_bot:
            return 100.0
        if len(ua) < 40:
            return 70.0
        if not any(b in ua for b in ('Mozilla', 'Chrome', 'Safari', 'Firefox')):
            return 50.0
        return 0.0

    @staticmethod
    def is_blacklisted(ua: str) -> bool:
        """Check against DB blacklist."""
        import re as _re
        from api.offer_inventory.models import UserAgentBlacklist

        ua_lower = ua.lower()
        for entry in UserAgentBlacklist.objects.filter(is_active=True):
            try:
                if entry.is_regex:
                    if _re.search(entry.pattern, ua, _re.IGNORECASE):
                        UserAgentBlacklist.objects.filter(id=entry.id).update(
                            match_count=entry.match_count + 1
                        )
                        return True
                else:
                    if entry.pattern.lower() in ua_lower:
                        return True
            except Exception:
                continue
        return False
