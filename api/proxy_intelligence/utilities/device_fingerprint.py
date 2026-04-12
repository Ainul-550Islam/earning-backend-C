"""
Device Fingerprint Processor  (PRODUCTION-READY - COMPLETE)
============================================================
Handles server-side processing of Canvas/JS/WebGL/Audio fingerprints
submitted from the frontend. Detects spoofing, links fingerprints to
users/IPs, and calculates device risk scores.

Frontend sends a POST with:
  {
    "canvas_hash":   "<sha256 of canvas data URL>",
    "webgl_hash":    "<sha256 of WebGL renderer string>",
    "audio_hash":    "<sha256 of AudioContext fingerprint>",
    "user_agent":    "...",
    "screen":        "1920x1080",
    "timezone":      "Asia/Dhaka",
    "language":      "en-US",
    "plugins":       ["PDF Viewer", ...],
    "fonts":         ["Arial", "Verdana", ...],
    "do_not_track":  "1",
    "cookie_enabled": true,
    "hardware_concurrency": 8,
    "device_memory":  8,
    "touch_points":   0,
    "platform":       "Win32"
  }
"""
import hashlib
import json
import logging
import re
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Known spoofing / bot User-Agent patterns ─────────────────────────────
BOT_UA_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'bot|crawler|spider|scraper|curl|wget|python-requests',
        r'headlesschrome|phantomjs|selenium|puppeteer|playwright',
        r'go-http-client|java/|okhttp|libwww-perl|mechanize',
    ]
]

# Canvas hashes known to be produced by headless browsers
HEADLESS_CANVAS_HASHES = {
    # Chrome headless default canvas fingerprint
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    # PhantomJS default
    '0000000000000000000000000000000000000000000000000000000000000000',
}

SUSPICIOUS_SCREEN_RESOLUTIONS = {
    '800x600', '1024x768',     # Common VM/bot defaults
    '1280x720', '1920x1080',   # Also legit — only suspicious in context
}

# Minimum number of fonts/plugins a real browser typically has
MIN_REAL_BROWSER_FONTS = 5
MIN_REAL_BROWSER_PLUGINS = 0  # Chrome removed plugins; not a strong signal alone


class DeviceFingerprintProcessor:
    """
    Processes raw fingerprint data from the frontend, creates/updates
    DeviceFingerprint records, and returns a risk assessment.
    """

    def __init__(self, raw_data: dict, ip_address: str = '',
                 user=None, tenant=None):
        self.raw = raw_data
        self.ip_address = ip_address
        self.user = user
        self.tenant = tenant
        self._spoofing_flags: list = []
        self._risk_score: int = 0

    # ── Public API ───────────────────────────────────────────────────────

    def process(self) -> dict:
        """
        Main entry point. Returns:
          - fingerprint_hash: stable composite hash
          - is_new: whether this is a new device
          - is_suspicious: whether spoofing was detected
          - risk_score: 0-100
          - flags: list of triggered signals
          - db_record: the DeviceFingerprint pk
        """
        composite_hash = self._build_composite_hash()
        self._run_spoofing_checks()

        db_record = self._upsert_fingerprint(composite_hash)

        return {
            'fingerprint_hash': composite_hash,
            'is_new':           db_record['created'],
            'is_suspicious':    self._risk_score >= 40,
            'spoofing_detected': len(self._spoofing_flags) > 0,
            'risk_score':       self._risk_score,
            'flags':            self._spoofing_flags,
            'device_type':      self._classify_device(),
            'browser_name':     self._parse_browser(),
            'os_name':          self._parse_os(),
            'db_id':            db_record['id'],
        }

    # ── Hash Building ────────────────────────────────────────────────────

    def _build_composite_hash(self) -> str:
        """
        Build a stable 64-char SHA-256 fingerprint hash from the
        most stable browser attributes (excludes volatile ones like IP).
        """
        stable_components = {
            'canvas':     self.raw.get('canvas_hash', ''),
            'webgl':      self.raw.get('webgl_hash', ''),
            'audio':      self.raw.get('audio_hash', ''),
            'ua':         self.raw.get('user_agent', ''),
            'screen':     self.raw.get('screen', ''),
            'timezone':   self.raw.get('timezone', ''),
            'language':   self.raw.get('language', ''),
            'platform':   self.raw.get('platform', ''),
            'hw_concurrency': str(self.raw.get('hardware_concurrency', '')),
            'device_memory':  str(self.raw.get('device_memory', '')),
            'touch_points':   str(self.raw.get('touch_points', '')),
            # Sort fonts/plugins for stability
            'fonts':      ','.join(sorted(self.raw.get('fonts', []))),
            'plugins':    ','.join(sorted(self.raw.get('plugins', []))),
        }
        payload = json.dumps(stable_components, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    # ── Spoofing Detection ───────────────────────────────────────────────

    def _run_spoofing_checks(self):
        """Run all spoofing detection checks and accumulate risk score."""
        self._check_bot_user_agent()
        self._check_canvas_hash()
        self._check_missing_components()
        self._check_javascript_inconsistencies()
        self._check_suspicious_resolution()
        self._check_webgl_renderer()
        self._check_fonts_count()

    def _check_bot_user_agent(self):
        ua = self.raw.get('user_agent', '')
        for pattern in BOT_UA_PATTERNS:
            if pattern.search(ua):
                self._flag('bot_user_agent', score=50)
                return

    def _check_canvas_hash(self):
        canvas_hash = self.raw.get('canvas_hash', '')
        # Empty canvas hash = JS fingerprinting was blocked or faked
        if not canvas_hash:
            self._flag('canvas_hash_missing', score=20)
            return
        # Known headless browser hashes
        if canvas_hash in HEADLESS_CANVAS_HASHES:
            self._flag('headless_canvas_hash', score=45)

    def _check_missing_components(self):
        """Real browsers always report certain fields."""
        required = ['user_agent', 'screen', 'timezone', 'language']
        missing = [f for f in required if not self.raw.get(f)]
        if missing:
            self._flag(f'missing_fields:{",".join(missing)}', score=15 * len(missing))

    def _check_javascript_inconsistencies(self):
        """
        Cross-check User-Agent claims vs JS-reported values.
        E.g. UA says Windows but platform says Linux.
        """
        ua = self.raw.get('user_agent', '').lower()
        platform = self.raw.get('platform', '').lower()

        if 'windows' in ua and 'linux' in platform:
            self._flag('ua_platform_mismatch', score=35)
        elif 'mac' in ua and 'win' in platform:
            self._flag('ua_platform_mismatch', score=35)
        elif 'linux' in ua and 'win32' in platform:
            self._flag('ua_platform_mismatch', score=35)

        # Mobile UA but touch_points = 0
        is_mobile_ua = any(kw in ua for kw in ['mobile', 'android', 'iphone', 'ipad'])
        touch_points = self.raw.get('touch_points', -1)
        if is_mobile_ua and touch_points == 0:
            self._flag('mobile_ua_no_touch', score=25)

    def _check_suspicious_resolution(self):
        screen = self.raw.get('screen', '')
        # VM default resolutions when combined with other signals
        if screen in {'800x600', '1024x768'} and len(self._spoofing_flags) > 0:
            self._flag('vm_default_resolution', score=15)

    def _check_webgl_renderer(self):
        """Check if WebGL renderer string indicates a VM or software renderer."""
        webgl_renderer = self.raw.get('webgl_renderer', '').lower()
        vm_renderers = [
            'swiftshader', 'llvmpipe', 'softpipe', 'mesa',
            'virtualbox', 'vmware', 'microsoft basic render driver',
        ]
        for renderer in vm_renderers:
            if renderer in webgl_renderer:
                self._flag(f'vm_webgl_renderer:{renderer}', score=30)
                break

    def _check_fonts_count(self):
        """Headless browsers typically have very few fonts."""
        fonts = self.raw.get('fonts', [])
        if isinstance(fonts, list) and 0 < len(fonts) < MIN_REAL_BROWSER_FONTS:
            self._flag('insufficient_fonts', score=20)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _flag(self, signal: str, score: int = 10):
        self._spoofing_flags.append(signal)
        self._risk_score = min(self._risk_score + score, 100)

    def _classify_device(self) -> str:
        ua = self.raw.get('user_agent', '').lower()
        if any(kw in ua for kw in ['mobile', 'android', 'iphone']):
            return 'mobile'
        if 'tablet' in ua or 'ipad' in ua:
            return 'tablet'
        return 'desktop'

    def _parse_browser(self) -> str:
        ua = self.raw.get('user_agent', '')
        if 'Firefox/' in ua:   return 'Firefox'
        if 'Edg/' in ua:       return 'Edge'
        if 'OPR/' in ua:       return 'Opera'
        if 'Chrome/' in ua:    return 'Chrome'
        if 'Safari/' in ua:    return 'Safari'
        return 'Unknown'

    def _parse_os(self) -> str:
        ua = self.raw.get('user_agent', '')
        if 'Windows' in ua:  return 'Windows'
        if 'Android' in ua:  return 'Android'
        if 'iPhone' in ua or 'iPad' in ua: return 'iOS'
        if 'Mac OS' in ua:   return 'macOS'
        if 'Linux' in ua:    return 'Linux'
        return 'Unknown'

    def _parse_browser_version(self) -> str:
        ua = self.raw.get('user_agent', '')
        match = re.search(r'(?:Chrome|Firefox|Safari|Edg|OPR)/(\d+\.\d+)', ua)
        return match.group(1) if match else ''

    # ── Database ─────────────────────────────────────────────────────────

    def _upsert_fingerprint(self, composite_hash: str) -> dict:
        """Create or update the DeviceFingerprint record."""
        from ..models import DeviceFingerprint

        defaults = {
            'user':            self.user,
            'user_agent':      self.raw.get('user_agent', ''),
            'browser_name':    self._parse_browser(),
            'browser_version': self._parse_browser_version(),
            'os_name':         self._parse_os(),
            'device_type':     self._classify_device(),
            'canvas_hash':     self.raw.get('canvas_hash', ''),
            'webgl_hash':      self.raw.get('webgl_hash', ''),
            'audio_hash':      self.raw.get('audio_hash', ''),
            'screen_resolution': self.raw.get('screen', ''),
            'timezone':        self.raw.get('timezone', ''),
            'language':        self.raw.get('language', ''),
            'plugins':         self.raw.get('plugins', []),
            'fonts':           self.raw.get('fonts', []),
            'last_seen':       timezone.now(),
            'ip_addresses':    self._merge_ip(composite_hash),
            'is_suspicious':   self._risk_score >= 40,
            'spoofing_detected': len(self._spoofing_flags) > 0,
            'risk_score':      self._risk_score,
            'tenant':          self.tenant,
        }

        obj, created = DeviceFingerprint.objects.update_or_create(
            fingerprint_hash=composite_hash,
            defaults=defaults,
        )

        if not created:
            obj.visit_count += 1
            obj.save(update_fields=['visit_count', 'last_seen',
                                    'risk_score', 'is_suspicious'])

        return {'id': str(obj.id), 'created': created}

    def _merge_ip(self, composite_hash: str) -> list:
        """Add current IP to the list of IPs seen with this fingerprint."""
        if not self.ip_address:
            return []
        from ..models import DeviceFingerprint
        existing = DeviceFingerprint.objects.filter(
            fingerprint_hash=composite_hash
        ).values_list('ip_addresses', flat=True).first()
        ip_list = existing if existing else []
        if self.ip_address not in ip_list:
            ip_list = list(ip_list) + [self.ip_address]
        return ip_list[-20:]  # Keep last 20 IPs


class FingerprintRiskAnalyzer:
    """
    Analyzes an existing DeviceFingerprint record for multi-account
    and cross-IP risk signals.
    """

    def __init__(self, fingerprint_hash: str, tenant=None):
        self.fingerprint_hash = fingerprint_hash
        self.tenant = tenant

    def analyze(self) -> dict:
        from ..models import DeviceFingerprint
        fp = DeviceFingerprint.objects.filter(
            fingerprint_hash=self.fingerprint_hash
        ).first()

        if not fp:
            return {'error': 'Fingerprint not found'}

        # How many distinct users share this fingerprint?
        from ..models import DeviceFingerprint
        from django.db.models import Count
        user_count = (
            DeviceFingerprint.objects
            .filter(fingerprint_hash=self.fingerprint_hash)
            .exclude(user=None)
            .values('user').distinct().count()
        )

        # How many distinct IPs?
        ip_count = len(fp.ip_addresses) if fp.ip_addresses else 0

        risk_additions = 0
        flags = []

        if user_count > 1:
            flags.append(f'shared_by_{user_count}_users')
            risk_additions += min(user_count * 15, 60)

        if ip_count > 10:
            flags.append(f'seen_on_{ip_count}_ips')
            risk_additions += min(ip_count * 3, 30)

        if fp.spoofing_detected:
            flags.append('spoofing_detected')
            risk_additions += 20

        final_risk = min(fp.risk_score + risk_additions, 100)

        return {
            'fingerprint_hash':  self.fingerprint_hash,
            'shared_users':      user_count,
            'seen_on_ips':       ip_count,
            'base_risk_score':   fp.risk_score,
            'final_risk_score':  final_risk,
            'is_high_risk':      final_risk >= 61,
            'flags':             flags,
            'visit_count':       fp.visit_count,
            'first_seen':        str(fp.first_seen),
            'last_seen':         str(fp.last_seen),
        }
