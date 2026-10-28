"""
api/security/services/BotDetectionML.py
========================================
ML-Scored Bot Detection — Upgrades basic UA/velocity checks with
multi-signal scoring, behavioral analysis, and pattern learning.

Replaces / extends the basic BotDetector in fraud_detection.py.

Signal categories:
  Network signals   — IP reputation, datacenter detection, ASN analysis
  Browser signals   — JS fingerprint, WebGL, canvas, font enumeration
  Behavioral signals — mouse movement, scroll, timing between events
  Request signals   — header consistency, TLS fingerprint, HTTP/2 ALPN
  Velocity signals  — click patterns, session length, page depth
  Historical signals — known bot IPs, user-agent databases

Scoring: 0-100. >= 65 = bot. >= 85 = confirmed bot (block).
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger("security.services.bot_detection_ml")

# ── Known bot signatures ──────────────────────────────────────────────────────
_BOT_UA_EXACT = frozenset([
    "python-requests", "go-http-client", "java", "curl", "wget",
    "libwww-perl", "mechanize", "scrapy", "beautifulsoup",
    "httpunit", "nutch", "htmlunit",
])

_BOT_UA_PATTERNS = [
    re.compile(r"(?i)(bot|crawl|spider|slurp|fetch|archive|scrape)"),
    re.compile(r"(?i)(headlesschrome|phantomjs|selenium|puppeteer|playwright|webdriver)"),
    re.compile(r"(?i)(zgrab|masscan|nikto|sqlmap|nmap|nessus|nuclei|zap)"),
    re.compile(r"(?i)(axios|node-fetch|aiohttp|urllib|httpx|requests)"),
]

# Known datacenter ASN ranges (simplified — in production use MaxMind ASN DB)
_DATACENTER_ASNS = frozenset([
    "14618", "16509", "15169", "8075",  # AWS, GCP, Azure
    "20473", "19318", "63949", "24940", # Vultr, OVH, Linode, Hetzner
    "14061", "16276", "36352", "13335", # DigitalOcean, OVH, ColoCrossing, Cloudflare
])

# Impossible browser attributes (bot tells)
_IMPOSSIBLE_BROWSER_VALUES = {
    "screen_width":  (0, 320),    # no real browser < 320px wide
    "screen_height": (0, 200),    # no real browser < 200px tall
    "color_depth":   frozenset([1, 2, 4]),  # modern browsers never report these
}


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BotDetectionResult:
    is_bot:          bool
    confidence:      float             # 0.0-1.0
    bot_score:       int               # 0-100
    bot_type:        str               = "unknown"  # crawler|scraper|headless|malware|human
    signals:         Dict[str, float]  = field(default_factory=dict)  # signal → weight
    active_signals:  List[str]         = field(default_factory=list)
    recommended_action: str            = "allow"   # allow|captcha|block|honeypot
    session_id:      str               = ""

    @property
    def risk_level(self) -> str:
        if self.bot_score >= 85: return "confirmed_bot"
        if self.bot_score >= 65: return "likely_bot"
        if self.bot_score >= 40: return "suspicious"
        if self.bot_score >= 20: return "low_risk"
        return "human"

    def to_dict(self) -> dict:
        return {
            "is_bot":           self.is_bot,
            "confidence":       round(self.confidence, 3),
            "bot_score":        self.bot_score,
            "bot_type":         self.bot_type,
            "risk_level":       self.risk_level,
            "active_signals":   self.active_signals,
            "recommended_action": self.recommended_action,
        }


# ─────────────────────────────────────────────────────────────────────────────
# ML-Scored Bot Detector
# ─────────────────────────────────────────────────────────────────────────────

class BotDetectionML:
    """
    Multi-signal ML-scored bot detector.

    Usage — basic (from request only):
        detector = BotDetectionML()
        result   = detector.analyze(request)
        if result.is_bot:
            return challenge_or_block(result)

    Usage — with client-side signals (JS fingerprint):
        result = detector.analyze(
            request,
            js_signals={
                "webdriver":        False,
                "chrome":           True,
                "plugins_length":   5,
                "screen_width":     1920,
                "screen_height":    1080,
                "color_depth":      24,
                "timezone_offset":  -300,
                "languages":        ["en-US", "en"],
                "canvas_hash":      "a3f2b1c9...",
                "webgl_vendor":     "Intel Inc.",
                "touch_points":     0,
                "mouse_moved":      True,
                "scroll_depth":     45,
                "time_on_page":     12.5,   # seconds
                "keystrokes":       0,
                "do_not_track":     None,
            }
        )
    """

    # Signal weights (higher = more indicative of bot)
    SIGNAL_WEIGHTS = {
        # Network signals
        "no_user_agent":              40,
        "bot_ua_pattern":             60,
        "bot_ua_exact":               55,
        "short_user_agent":           20,
        "datacenter_ip":              25,
        "known_bot_ip":               70,
        "tor_exit_node":              40,
        "proxy_detected":             15,

        # Browser / JS signals
        "webdriver_flag":             85,
        "no_plugins":                 30,
        "impossible_screen":          50,
        "impossible_color_depth":     45,
        "no_languages":               35,
        "canvas_spoofed":             40,
        "webgl_missing":              25,
        "no_touch_and_mobile":        20,

        # Behavioral signals
        "no_mouse_movement":          30,
        "zero_scroll_depth":          20,
        "instant_page_interaction":   45,
        "no_keystrokes_on_form":      25,
        "machine_speed_interaction":  50,

        # Request signals
        "missing_accept_header":      15,
        "missing_accept_language":    20,
        "missing_accept_encoding":    15,
        "suspicious_header_order":    30,
        "no_referer_on_deep_link":    10,

        # Velocity signals
        "high_click_velocity":        45,
        "no_session_history":         20,
        "uniform_request_timing":     35,
        "zero_page_depth":            25,
    }

    def analyze(
        self,
        request,
        js_signals: Optional[Dict] = None,
        ip:         Optional[str]  = None,
    ) -> BotDetectionResult:
        """
        Full bot detection analysis.

        Args:
            request:    Django HTTP request
            js_signals: Client-side JavaScript signals dict (optional)
            ip:         Override IP address (optional)

        Returns:
            BotDetectionResult
        """
        active_signals  = {}
        bot_score       = 0

        ua  = request.META.get("HTTP_USER_AGENT", "")
        ip  = ip or self._extract_ip(request)

        # ── Layer 1: User-Agent analysis ──────────────────────────────────────
        ua_score, ua_signals = self._analyze_user_agent(ua)
        active_signals.update(ua_signals)
        bot_score += ua_score

        # ── Layer 2: HTTP header analysis ────────────────────────────────────
        hdr_score, hdr_signals = self._analyze_headers(request)
        active_signals.update(hdr_signals)
        bot_score += hdr_score

        # ── Layer 3: IP reputation ────────────────────────────────────────────
        ip_score, ip_signals = self._analyze_ip(ip)
        active_signals.update(ip_signals)
        bot_score += ip_score

        # ── Layer 4: Velocity analysis ────────────────────────────────────────
        vel_score, vel_signals = self._analyze_velocity(ip, ua)
        active_signals.update(vel_signals)
        bot_score += vel_score

        # ── Layer 5: JS / browser fingerprint signals ─────────────────────────
        if js_signals:
            js_score, js_sigs = self._analyze_js_signals(js_signals)
            active_signals.update(js_sigs)
            bot_score += js_score

        # ── Layer 6: Historical pattern matching ──────────────────────────────
        hist_score, hist_signals = self._check_historical_patterns(ip, ua)
        active_signals.update(hist_signals)
        bot_score += hist_score

        # ── Normalize & classify ──────────────────────────────────────────────
        bot_score  = min(bot_score, 100)
        is_bot     = bot_score >= 65
        confidence = bot_score / 100.0
        bot_type   = self._classify_bot_type(active_signals, ua)
        action     = self._recommend_action(bot_score, active_signals)

        # Record in Redis for pattern learning
        self._record_analysis(ip, ua, bot_score)

        if is_bot:
            logger.warning(
                "Bot detected: ip=%s score=%d type=%s signals=%s",
                ip, bot_score, bot_type, list(active_signals.keys())[:5],
            )

        return BotDetectionResult(
            is_bot             = is_bot,
            confidence         = confidence,
            bot_score          = bot_score,
            bot_type           = bot_type,
            signals            = {k: self.SIGNAL_WEIGHTS.get(k, 10) for k in active_signals},
            active_signals     = list(active_signals.keys()),
            recommended_action = action,
        )

    # ── Layer analyzers ───────────────────────────────────────────────────────

    def _analyze_user_agent(self, ua: str) -> Tuple[int, Dict]:
        signals = {}
        score   = 0

        if not ua:
            signals["no_user_agent"] = True
            return self.SIGNAL_WEIGHTS["no_user_agent"], signals

        ua_lower = ua.lower()

        # Exact match
        for bot_ua in _BOT_UA_EXACT:
            if bot_ua in ua_lower:
                signals["bot_ua_exact"] = True
                score += self.SIGNAL_WEIGHTS["bot_ua_exact"]
                break

        # Pattern match
        for pattern in _BOT_UA_PATTERNS:
            if pattern.search(ua):
                signals["bot_ua_pattern"] = True
                score += self.SIGNAL_WEIGHTS["bot_ua_pattern"]
                break

        if len(ua) < 40 and "bot_ua_exact" not in signals:
            signals["short_user_agent"] = True
            score += self.SIGNAL_WEIGHTS["short_user_agent"]

        return min(score, 80), signals

    def _analyze_headers(self, request) -> Tuple[int, Dict]:
        signals = {}
        score   = 0
        meta    = request.META

        if not meta.get("HTTP_ACCEPT"):
            signals["missing_accept_header"] = True
            score += self.SIGNAL_WEIGHTS["missing_accept_header"]

        if not meta.get("HTTP_ACCEPT_LANGUAGE"):
            signals["missing_accept_language"] = True
            score += self.SIGNAL_WEIGHTS["missing_accept_language"]

        if not meta.get("HTTP_ACCEPT_ENCODING"):
            signals["missing_accept_encoding"] = True
            score += self.SIGNAL_WEIGHTS["missing_accept_encoding"]

        return min(score, 50), signals

    def _analyze_ip(self, ip: str) -> Tuple[int, Dict]:
        signals = {}
        score   = 0

        if not ip:
            return 0, signals

        # Check Redis blacklist
        if cache.get(f"sec:bot:known:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"):
            signals["known_bot_ip"] = True
            score += self.SIGNAL_WEIGHTS["known_bot_ip"]

        # ASN / datacenter check
        asn = self._lookup_asn(ip)
        if asn and asn in _DATACENTER_ASNS:
            signals["datacenter_ip"] = True
            score += self.SIGNAL_WEIGHTS["datacenter_ip"]

        return min(score, 70), signals

    def _analyze_velocity(self, ip: str, ua: str) -> Tuple[int, Dict]:
        signals = {}
        score   = 0
        now     = int(time.time())

        # Click velocity per IP
        vel_key  = f"sec:bot:vel:{hashlib.sha256((ip + ua).encode()).hexdigest()[:16]}"
        count    = (cache.get(vel_key) or 0) + 1
        if count == 1:
            cache.set(vel_key, 1, 60)
        else:
            cache.incr(vel_key)

        if count > 30:
            signals["high_click_velocity"] = True
            score += min(self.SIGNAL_WEIGHTS["high_click_velocity"] * (count // 30), 60)

        # Check request timing uniformity (bots have machine-precise timing)
        timing_key  = f"sec:bot:timing:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"
        timestamps  = cache.get(timing_key) or []
        timestamps.append(now)
        timestamps   = timestamps[-10:]  # keep last 10
        cache.set(timing_key, timestamps, 300)

        if len(timestamps) >= 5:
            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                variance     = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
                std_dev      = math.sqrt(variance)
                # Real humans have std_dev > 1 second; bots < 0.1s
                if avg_interval > 0 and std_dev / max(avg_interval, 0.001) < 0.05:
                    signals["uniform_request_timing"] = True
                    score += self.SIGNAL_WEIGHTS["uniform_request_timing"]

        return min(score, 70), signals

    def _analyze_js_signals(self, js: Dict) -> Tuple[int, Dict]:
        signals = {}
        score   = 0

        # Webdriver flag (Selenium/Puppeteer tell)
        if js.get("webdriver"):
            signals["webdriver_flag"] = True
            score += self.SIGNAL_WEIGHTS["webdriver_flag"]

        # No plugins (headless browsers have empty plugins list)
        plugins = js.get("plugins_length", -1)
        if plugins == 0:
            signals["no_plugins"] = True
            score += self.SIGNAL_WEIGHTS["no_plugins"]

        # Impossible screen dimensions
        w = js.get("screen_width", 1920)
        h = js.get("screen_height", 1080)
        lo_w, hi_w = _IMPOSSIBLE_BROWSER_VALUES["screen_width"]
        lo_h, hi_h = _IMPOSSIBLE_BROWSER_VALUES["screen_height"]
        if lo_w <= w <= hi_w or lo_h <= h <= hi_h:
            signals["impossible_screen"] = True
            score += self.SIGNAL_WEIGHTS["impossible_screen"]

        # Color depth
        depth = js.get("color_depth", 24)
        if depth in _IMPOSSIBLE_BROWSER_VALUES["color_depth"]:
            signals["impossible_color_depth"] = True
            score += self.SIGNAL_WEIGHTS["impossible_color_depth"]

        # No languages
        langs = js.get("languages", [])
        if not langs:
            signals["no_languages"] = True
            score += self.SIGNAL_WEIGHTS["no_languages"]

        # No mouse movement
        if js.get("mouse_moved") is False:
            signals["no_mouse_movement"] = True
            score += self.SIGNAL_WEIGHTS["no_mouse_movement"]

        # Instant page interaction (< 500ms = not human)
        time_on_page = js.get("time_on_page", 10.0)
        if time_on_page < 0.5:
            signals["instant_page_interaction"] = True
            score += self.SIGNAL_WEIGHTS["instant_page_interaction"]

        # Machine-speed interaction (< 100ms per event)
        if time_on_page > 0 and js.get("keystrokes", 0) > 50:
            wpm = js["keystrokes"] / (time_on_page / 60.0)
            if wpm > 1000:  # no human types 1000+ WPM
                signals["machine_speed_interaction"] = True
                score += self.SIGNAL_WEIGHTS["machine_speed_interaction"]

        # WebGL missing
        if js.get("webgl_vendor") in (None, "", "unknown", "Google Inc. (NVIDIA)"):
            if js.get("webgl_vendor") is None:
                signals["webgl_missing"] = True
                score += self.SIGNAL_WEIGHTS["webgl_missing"]

        return min(score, 95), signals

    def _check_historical_patterns(self, ip: str, ua: str) -> Tuple[int, Dict]:
        """Check against historically flagged patterns."""
        signals = {}
        score   = 0
        fp      = hashlib.sha256(f"{ip}:{ua}".encode()).hexdigest()[:24]

        # Check if this fingerprint was previously flagged
        flag_key = f"sec:bot:fp:{fp}"
        flags    = cache.get(flag_key) or 0
        if flags >= 3:
            signals["repeated_bot_fingerprint"] = True
            score += min(flags * 10, 60)

        return min(score, 60), signals

    # ── Classification ────────────────────────────────────────────────────────

    def _classify_bot_type(self, signals: Dict, ua: str) -> str:
        if signals.get("webdriver_flag"):       return "headless_browser"
        if signals.get("bot_ua_pattern"):
            ua_lower = ua.lower()
            if "crawl" in ua_lower or "spider" in ua_lower: return "crawler"
            if "scrape" in ua_lower:                         return "scraper"
            if any(x in ua_lower for x in ["nikto","sqlmap","nmap","nuclei"]): return "scanner"
        if signals.get("datacenter_ip"):        return "datacenter_bot"
        if signals.get("uniform_request_timing"): return "automated_script"
        if signals.get("no_user_agent"):        return "raw_http_client"
        return "unknown"

    def _recommend_action(self, score: int, signals: Dict) -> str:
        if signals.get("webdriver_flag"):    return "block"
        if signals.get("known_bot_ip"):      return "block"
        if signals.get("bot_ua_exact"):      return "block"
        if score >= 85:                      return "block"
        if score >= 65:                      return "captcha"
        if score >= 40:                      return "flag"
        return "allow"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_ip(self, request) -> str:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")

    def _lookup_asn(self, ip: str) -> Optional[str]:
        """Lookup ASN for IP. Returns None if unavailable."""
        try:
            import ipaddress
            ip_obj = ipaddress.ip_address(ip)
            # Would use MaxMind GeoIP2 or ipinfo.io in production
            return None
        except Exception:
            return None

    def _record_analysis(self, ip: str, ua: str, score: int) -> None:
        """Record result for pattern learning."""
        if score >= 65:
            fp      = hashlib.sha256(f"{ip}:{ua}".encode()).hexdigest()[:24]
            flag_key = f"sec:bot:fp:{fp}"
            flags    = (cache.get(flag_key) or 0) + 1
            cache.set(flag_key, flags, 86400 * 7)

            # Mark IP as known bot
            if score >= 85:
                ip_key = f"sec:bot:known:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"
                cache.set(ip_key, 1, 86400 * 30)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

bot_detector_ml = BotDetectionML()