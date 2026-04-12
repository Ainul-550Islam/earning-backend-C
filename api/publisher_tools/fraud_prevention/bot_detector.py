# api/publisher_tools/fraud_prevention/bot_detector.py
"""Bot Detector — Multi-layer bot traffic detection."""
import re
from typing import Dict, List

KNOWN_BOT_SIGNATURES = [
    r"googlebot", r"bingbot", r"slurp", r"duckduckbot", r"baiduspider",
    r"yandexbot", r"sogou", r"exabot", r"facebot", r"ia_archiver",
    r"wget", r"curl", r"python-requests", r"java/", r"scrapy",
    r"selenium", r"phantomjs", r"headlesschrome", r"puppeteer",
    r"playwright", r"zombie\.js", r"casperjs", r"go-http-client",
    r"libwww-perl", r"lwp-trivial", r"okhttp", r"python-urllib",
]

BOT_PATTERN = re.compile("|".join(KNOWN_BOT_SIGNATURES), re.IGNORECASE)

MISSING_HEADER_SUSPICIOUS = ["Accept", "Accept-Language", "Accept-Encoding"]
SUSPICIOUS_ACCEPT_PATTERNS = ["*/*", "text/html,*/*;q=0.1"]


def detect_bot_from_ua(user_agent: str) -> Dict:
    if not user_agent or len(user_agent) < 10:
        return {"is_bot": True, "confidence": 90, "reason": "missing_or_short_ua", "score": 90}
    if BOT_PATTERN.search(user_agent):
        matched = BOT_PATTERN.search(user_agent).group(0)
        return {"is_bot": True, "confidence": 99, "reason": f"known_bot_signature:{matched}", "score": 99}
    score = 0
    reasons = []
    if re.search(r"bot|crawler|spider|scraper|checker", user_agent, re.IGNORECASE):
        score += 40; reasons.append("bot_keyword_in_ua")
    if re.search(r"^[A-Z]", user_agent) and "/" not in user_agent:
        score += 20; reasons.append("uppercase_start_no_version")
    if len(user_agent) < 30:
        score += 15; reasons.append("very_short_ua")
    if re.search(r"(^Mozilla/4\.0 \(compatible\)$)|(^Java/)", user_agent):
        score += 35; reasons.append("old_generic_ua")
    return {"is_bot": score >= 50, "confidence": min(100, score + 10), "reason": ",".join(reasons) or "clean", "score": score}


def detect_headless_browser(ua: str, headers: dict) -> Dict:
    score = 0
    reasons = []
    if re.search(r"HeadlessChrome|Headless", ua, re.IGNORECASE):
        score += 80; reasons.append("headless_chrome_ua")
    if not headers.get("Accept-Language"):
        score += 20; reasons.append("missing_accept_language")
    if not headers.get("Accept"):
        score += 20; reasons.append("missing_accept")
    if headers.get("Accept") == "*/*":
        score += 15; reasons.append("wildcard_accept")
    return {"is_headless": score >= 50, "score": score, "reasons": reasons}


def is_datacenter_ip(ip_address: str) -> bool:
    datacenter_prefixes = ["104.16.", "104.17.", "13.", "52.", "54.", "35.", "34.", "40.", "20.", "23."]
    return any(ip_address.startswith(p) for p in datacenter_prefixes)
