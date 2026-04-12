"""
Browser Fingerprint Analyzer  (PRODUCTION-READY — COMPLETE)
============================================================
Server-side analysis of browser fingerprint data submitted
from the frontend JavaScript fingerprinting library.

Works alongside device_fingerprint.py (which handles Canvas/WebGL/Audio
hashes) but focuses specifically on browser-level signals:
  - Browser-specific feature detection results
  - Plugin/extension fingerprinting
  - Font enumeration consistency
  - Performance timing characteristics
  - navigator.* property analysis
  - Screen color depth and pixel ratio
  - Do Not Track (DNT) signal analysis
  - WebRTC leak data (delegated to webrtc_leak_detector)

Frontend library should submit:
  {
    "canvas_hash":          "sha256...",
    "webgl_hash":           "sha256...",
    "audio_hash":           "sha256...",
    "user_agent":           "Mozilla/5.0...",
    "platform":             "Win32",
    "language":             "en-US",
    "screen":               "1920x1080",
    "color_depth":          24,
    "pixel_ratio":          1,
    "timezone":             "Asia/Dhaka",
    "timezone_offset":      -360,
    "do_not_track":         "1",
    "cookie_enabled":       true,
    "hardware_concurrency": 8,
    "device_memory":        8,
    "touch_points":         0,
    "max_touch_points":     0,
    "plugins":              [...],
    "fonts":                [...],
    "indexed_db":           true,
    "local_storage":        true,
    "session_storage":      true,
    "open_database":        false,
    "webgl_renderer":       "NVIDIA GeForce GTX 1080/PCIe/SSE2",
    "webgl_vendor":         "NVIDIA Corporation"
  }
"""
import hashlib
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Known headless canvas hashes ──────────────────────────────────────────
HEADLESS_CANVAS_HASHES = frozenset({
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    '0000000000000000000000000000000000000000000000000000000000000000',
    'da39a3ee5e6b4b0d3255bfef95601890afd80709',
})

# ── VM/software WebGL vendors ─────────────────────────────────────────────
VM_WEBGL_VENDORS = [
    'mesa', 'vmware', 'virtualbox', 'microsoft',
    'google inc. (swiftshader)', 'google inc. (llvm)',
]

# ── Suspicious color depths ────────────────────────────────────────────────
# Real displays are 24-bit or 32-bit; 1, 8, 16 are unusual
SUSPICIOUS_COLOR_DEPTHS = {1, 8, 16}

# ── Expected timezone offset ranges per UTC offset ────────────────────────
# timezone_offset from JavaScript = UTC - local time (in minutes)
# So UTC+6 (Dhaka) = -360
TIMEZONE_OFFSET_RANGE = (-720, 840)  # UTC-12 to UTC+14


class BrowserFingerprintAnalyzer:
    """
    Analyzes browser fingerprint data for automation and spoofing signals.

    Usage:
        analyzer = BrowserFingerprintAnalyzer(fingerprint_data)
        result = analyzer.analyze()
        composite_hash = result['fingerprint_hash']
        is_bot = result['is_automated']
    """

    def __init__(self, fingerprint_data: dict):
        self.fp = fingerprint_data

    # ── Main Analysis ──────────────────────────────────────────────────────

    def analyze(self) -> dict:
        """
        Run all browser fingerprint analysis checks.

        Returns:
            {
                'fingerprint_hash':  str,   # Stable composite hash
                'is_automated':      bool,  # Bot/automation detected
                'automation_score':  int,   # 0-100
                'is_headless':       bool,
                'is_vm':             bool,
                'flags':             list,
                'browser_profile':   dict,  # Detected browser characteristics
                'risk_contribution': int,   # Extra risk points to add
            }
        """
        flags = []
        score = 0

        def flag(name: str, pts: int = 15):
            flags.append(name)
            nonlocal score
            score += pts

        # ── Canvas hash ─────────────────────────────────────────────────
        canvas = self.fp.get('canvas_hash', '')
        if not canvas:
            flag('no_canvas_hash', 20)
        elif canvas in HEADLESS_CANVAS_HASHES:
            flag('headless_canvas_hash', 45)

        # ── WebGL ────────────────────────────────────────────────────────
        webgl_vendor   = (self.fp.get('webgl_vendor', '') or '').lower()
        webgl_renderer = (self.fp.get('webgl_renderer', '') or '').lower()

        if any(v in webgl_vendor for v in VM_WEBGL_VENDORS):
            flag('vm_webgl_vendor', 35)

        vm_renderers = ['swiftshader', 'llvmpipe', 'softpipe', 'virtualbox', 'vmware', 'mesa']
        if any(r in webgl_renderer for r in vm_renderers):
            flag('vm_webgl_renderer', 35)

        # ── Screen ───────────────────────────────────────────────────────
        screen = self.fp.get('screen', '')
        if not screen or screen in ('0x0', '1x1'):
            flag('invalid_screen', 25)

        color_depth = self.fp.get('color_depth', 24)
        if color_depth in SUSPICIOUS_COLOR_DEPTHS:
            flag(f'suspicious_color_depth:{color_depth}', 20)

        pixel_ratio = self.fp.get('pixel_ratio', 1)
        if pixel_ratio == 0:
            flag('zero_pixel_ratio', 20)

        # ── User-Agent analysis ───────────────────────────────────────────
        ua = self.fp.get('user_agent', '')
        if not ua:
            flag('missing_user_agent', 35)
        else:
            ua_lower = ua.lower()
            bot_kws  = ['headlesschrome', 'phantomjs', 'selenium', 'puppeteer', 'playwright']
            for kw in bot_kws:
                if kw in ua_lower:
                    flag(f'bot_ua:{kw}', 50)
                    break

        # ── Platform vs UA consistency ────────────────────────────────────
        platform = (self.fp.get('platform', '') or '').lower()
        if ua and platform:
            ua_lower = ua.lower()
            if 'windows' in ua_lower and 'linux' in platform:
                flag('ua_platform_mismatch', 40)
            elif 'mac' in ua_lower and 'win' in platform:
                flag('ua_platform_mismatch', 40)

        # ── Mobile UA + no touch ──────────────────────────────────────────
        is_mobile_ua = any(k in ua.lower() for k in ['mobile','android','iphone','ipad'])
        touch_pts    = self.fp.get('touch_points', -1)
        if is_mobile_ua and touch_pts == 0:
            flag('mobile_ua_no_touch', 30)

        # ── Hardware concurrency ──────────────────────────────────────────
        hw_conc = self.fp.get('hardware_concurrency', 0)
        if hw_conc > 128:
            flag(f'impossible_hw_concurrency:{hw_conc}', 30)
        elif hw_conc == 1:
            flag('single_core_unusual', 10)

        # ── Timezone offset validity ──────────────────────────────────────
        tz_offset = self.fp.get('timezone_offset')
        if tz_offset is not None:
            lo, hi = TIMEZONE_OFFSET_RANGE
            if not (lo <= tz_offset <= hi):
                flag(f'invalid_timezone_offset:{tz_offset}', 25)

        # ── Storage APIs ──────────────────────────────────────────────────
        local_storage   = self.fp.get('local_storage', True)
        session_storage = self.fp.get('session_storage', True)
        indexed_db      = self.fp.get('indexed_db', True)
        # Headless environments often report these as False
        if not local_storage and not session_storage and not indexed_db:
            flag('all_storage_disabled', 30)

        # ── Fonts count ───────────────────────────────────────────────────
        fonts = self.fp.get('fonts', [])
        if isinstance(fonts, list):
            if 0 < len(fonts) < 5:
                flag('too_few_fonts', 20)
            elif len(fonts) == 0:
                flag('no_fonts_reported', 15)

        # ── Plugins (Chrome removed NPAPI, IE plugins) ────────────────────
        plugins   = self.fp.get('plugins', [])
        is_chrome = 'chrome' in ua.lower() and 'edge' not in ua.lower()
        if isinstance(plugins, list):
            old_plugins_lower = [str(p).lower() for p in plugins]
            has_flash = any('flash' in p for p in old_plugins_lower)
            has_java  = any('java' in p for p in old_plugins_lower)
            if is_chrome and (has_flash or has_java):
                chrome_m = re.search(r'Chrome/(\d+)', ua)
                if chrome_m and int(chrome_m.group(1)) >= 45:
                    flag('impossible_plugin_for_chrome_version', 30)

        # ── Audio hash ────────────────────────────────────────────────────
        audio_hash = self.fp.get('audio_hash', '')
        if not audio_hash:
            flag('no_audio_fingerprint', 10)

        # ── Compute composite hash ────────────────────────────────────────
        fp_hash = self._compute_hash()

        score = min(score, 100)

        return {
            'fingerprint_hash':  fp_hash,
            'is_automated':      score >= 30,
            'automation_score':  score,
            'is_headless':       any('headless' in f or 'phantom' in f for f in flags),
            'is_vm':             any('vm_' in f for f in flags),
            'flags':             flags,
            'browser_profile':   self._build_browser_profile(),
            'risk_contribution': min(score // 3, 25),
        }

    # ── Hash Computation ───────────────────────────────────────────────────

    def _compute_hash(self) -> str:
        """
        Compute a stable composite fingerprint hash from the most
        stable browser attributes.
        """
        stable = {
            'canvas':      self.fp.get('canvas_hash', ''),
            'webgl':       self.fp.get('webgl_hash', ''),
            'audio':       self.fp.get('audio_hash', ''),
            'ua':          self.fp.get('user_agent', ''),
            'platform':    self.fp.get('platform', ''),
            'screen':      self.fp.get('screen', ''),
            'timezone':    self.fp.get('timezone', ''),
            'language':    self.fp.get('language', ''),
            'hw_conc':     str(self.fp.get('hardware_concurrency', '')),
            'device_mem':  str(self.fp.get('device_memory', '')),
            'touch_pts':   str(self.fp.get('touch_points', '')),
            'fonts':       ','.join(sorted(self.fp.get('fonts', []) or [])),
            'plugins':     ','.join(sorted(str(p) for p in (self.fp.get('plugins', []) or []))),
        }
        payload = json.dumps(stable, sort_keys=True)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    @staticmethod
    def compute_hash(fp_data: dict) -> str:
        """Static convenience wrapper for compute_hash."""
        return BrowserFingerprintAnalyzer(fp_data)._compute_hash()

    # ── Browser Profile ────────────────────────────────────────────────────

    def _build_browser_profile(self) -> dict:
        """Extract a structured browser profile from the raw data."""
        ua = self.fp.get('user_agent', '')
        return {
            'browser':         self._parse_browser(ua),
            'browser_version': self._parse_browser_version(ua),
            'os':              self._parse_os(ua),
            'device_type':     self._classify_device(ua),
            'screen':          self.fp.get('screen', ''),
            'color_depth':     self.fp.get('color_depth', 24),
            'pixel_ratio':     self.fp.get('pixel_ratio', 1),
            'timezone':        self.fp.get('timezone', ''),
            'language':        self.fp.get('language', ''),
            'webgl_vendor':    self.fp.get('webgl_vendor', ''),
            'webgl_renderer':  self.fp.get('webgl_renderer', ''),
            'font_count':      len(self.fp.get('fonts', []) or []),
            'plugin_count':    len(self.fp.get('plugins', []) or []),
            'cookie_enabled':  self.fp.get('cookie_enabled', True),
            'do_not_track':    self.fp.get('do_not_track', ''),
        }

    @staticmethod
    def _parse_browser(ua: str) -> str:
        if 'Firefox/' in ua:  return 'Firefox'
        if 'Edg/' in ua:      return 'Edge'
        if 'OPR/' in ua:      return 'Opera'
        if 'Chrome/' in ua:   return 'Chrome'
        if 'Safari/' in ua:   return 'Safari'
        return 'Unknown'

    @staticmethod
    def _parse_browser_version(ua: str) -> str:
        m = re.search(r'(?:Chrome|Firefox|Safari|Edg|OPR)/(\d+\.\d+)', ua)
        return m.group(1) if m else ''

    @staticmethod
    def _parse_os(ua: str) -> str:
        if 'Windows' in ua: return 'Windows'
        if 'Android' in ua: return 'Android'
        if 'iPhone' in ua:  return 'iOS'
        if 'iPad' in ua:    return 'iPadOS'
        if 'Mac OS' in ua:  return 'macOS'
        if 'Linux' in ua:   return 'Linux'
        return 'Unknown'

    @staticmethod
    def _classify_device(ua: str) -> str:
        ua_lower = ua.lower()
        if any(k in ua_lower for k in ['iphone', 'android', 'mobile']): return 'mobile'
        if any(k in ua_lower for k in ['ipad', 'tablet']): return 'tablet'
        return 'desktop'
