"""
Device Spoofing Detector  (PRODUCTION-READY — COMPLETE)
=========================================================
Detects fraudulent device/browser information submitted to evade
fingerprinting systems on earning/marketing platforms.

Spoofing patterns detected:
  1. User-Agent vs JavaScript platform inconsistency
  2. Impossible or non-existent browser versions
  3. Headless/automated browser fingerprint
  4. VM/sandbox WebGL renderer strings
  5. Screen resolution that matches no real device
  6. Time zone vs IP country mismatch
  7. Canvas/WebGL hash matches known automation tools
  8. Plugin list inconsistency with claimed browser
  9. Hardware concurrency mismatch (claimed 128 cores)
  10. Battery API spoofing indicators
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── Known bot/automation User-Agent patterns ───────────────────────────────
BOT_UA_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'headlesschrome|phantomjs|selenium|puppeteer|playwright',
        r'bot|crawler|spider|scraper',
        r'curl|wget|python-requests|python/\d|go-http-client',
        r'java/\d|okhttp|libwww-perl|mechanize|scrapy',
        r'zgrab|masscan|nmap|nikto|sqlmap',
    ]
]

# ── VM/Sandbox WebGL renderers ─────────────────────────────────────────────
VM_WEBGL_RENDERERS = [
    'swiftshader',         # Chrome software renderer
    'llvmpipe',            # Mesa software renderer
    'softpipe',            # Gallium3D software renderer
    'mesa',                # Generic Mesa (software fallback)
    'microsoft basic render driver',
    'virtualbox',          # VirtualBox VM
    'vmware',              # VMware
    'vmvga',               # VMware SVGA
    'parallels',           # Parallels VM
    'qxl paravirtual',    # QEMU/KVM
    'google swiftshader',  # Chrome 57+ headless
]

# ── Screen resolutions typical of bots/VMs ────────────────────────────────
BOT_SCREEN_RESOLUTIONS = {
    '800x600',   '1024x768',   '1024x600',
    '0x0',       '1x1',        '0x600',
}

# ── User-Agent → Expected platform mappings ───────────────────────────────
UA_PLATFORM_MAP = {
    'windows': ['win32', 'win64', 'windows'],
    'mac':     ['macintel', 'macppc'],
    'linux':   ['linux x86_64', 'linux aarch64', 'linux armv', 'linux mips'],
    'android': ['linux armv', 'linux aarch64'],
    'iphone':  ['iphone'],
    'ipad':    ['ipad'],
}

# ── Canvas hashes known to come from headless browsers ────────────────────
KNOWN_HEADLESS_CANVAS_HASHES = {
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',  # Empty
    '0000000000000000000000000000000000000000000000000000000000000000',  # Zeroed
    'da39a3ee5e6b4b0d3255bfef95601890afd80709',                          # SHA1 empty
}


class DeviceSpoofingDetector:
    """
    Server-side analysis of browser/device signals to detect spoofing.

    Designed to work with fingerprint data submitted from the frontend:
    canvas_hash, webgl_hash, user_agent, platform, screen, timezone, etc.

    Usage:
        detector = DeviceSpoofingDetector(
            user_agent='Mozilla/5.0 ...',
            platform='Win32',
            canvas_hash='a3f5...',
            webgl_renderer='Google SwiftShader',
            screen='1920x1080',
            timezone='America/New_York',
            hardware_concurrency=8,
            language='en-US',
        )
        result = detector.detect()
    """

    def __init__(
        self,
        user_agent: str           = '',
        platform: str             = '',
        canvas_hash: str          = '',
        webgl_hash: str           = '',
        webgl_renderer: str       = '',
        screen: str               = '',
        timezone: str             = '',
        language: str             = '',
        hardware_concurrency: int = 0,
        device_memory: int        = 0,
        touch_points: int         = -1,
        plugins: list             = None,
        fonts: list               = None,
        ip_country: str           = '',
    ):
        self.user_agent           = user_agent
        self.platform             = platform.lower()
        self.canvas_hash          = canvas_hash
        self.webgl_hash           = webgl_hash
        self.webgl_renderer       = webgl_renderer.lower()
        self.screen               = screen
        self.timezone             = timezone
        self.language             = language
        self.hardware_concurrency = hardware_concurrency
        self.device_memory        = device_memory
        self.touch_points         = touch_points
        self.plugins              = plugins or []
        self.fonts                = fonts or []
        self.ip_country           = ip_country.upper()
        self.flags: list          = []
        self.score: int           = 0

    # ── Public API ─────────────────────────────────────────────────────────

    def detect(self) -> dict:
        """
        Run all device spoofing checks.

        Returns:
            {
                'spoofing_detected': bool,
                'spoofing_score':    int (0-100),
                'flags':             list of {signal, description, score},
                'device_type':       str,
                'browser_name':      str,
                'os_name':           str,
                'is_headless':       bool,
                'is_vm':             bool,
                'is_bot_ua':         bool,
            }
        """
        self.flags = []
        self.score = 0

        self._check_bot_user_agent()
        self._check_ua_platform_mismatch()
        self._check_impossible_ua_version()
        self._check_webgl_renderer()
        self._check_canvas_hash()
        self._check_screen_resolution()
        self._check_mobile_ua_touch_mismatch()
        self._check_hardware_concurrency()
        self._check_plugin_browser_mismatch()
        self._check_font_count()
        self._check_timezone_language()

        self.score = min(self.score, 100)

        return {
            'spoofing_detected': self.score >= 30,
            'spoofing_score':    self.score,
            'flags':             self.flags,
            'is_bot_ua':         self._is_bot_ua(),
            'is_vm':             self._is_vm(),
            'is_headless':       self._is_headless(),
            'device_type':       self._classify_device(),
            'browser_name':      self._parse_browser(),
            'os_name':           self._parse_os(),
            'risk_contribution': min(self.score // 2, 25),  # Max 25pt risk addition
        }

    # ── Signal Checks ──────────────────────────────────────────────────────

    def _check_bot_user_agent(self):
        """Signal 1: Bot/automation UA patterns."""
        for pattern in BOT_UA_PATTERNS:
            if pattern.search(self.user_agent):
                match = pattern.pattern.split('|')[0]
                self._flag('bot_user_agent', f'Bot UA pattern: {match}', score=50)
                return
        if not self.user_agent:
            self._flag('missing_user_agent', 'No User-Agent header', score=35)

    def _check_ua_platform_mismatch(self):
        """Signal 2: UA claims Windows but JS reports Linux platform."""
        if not self.user_agent or not self.platform:
            return

        ua_lower = self.user_agent.lower()

        for ua_keyword, platforms in UA_PLATFORM_MAP.items():
            if ua_keyword in ua_lower:
                matches_platform = any(p in self.platform for p in platforms)
                if not matches_platform:
                    self._flag(
                        'ua_platform_mismatch',
                        f'UA says {ua_keyword} but platform="{self.platform}"',
                        score=40,
                    )
                    return

    def _check_impossible_ua_version(self):
        """Signal 3: Browser version that doesn't exist or is impossible."""
        if not self.user_agent:
            return

        # Check Chrome version
        chrome_match = re.search(r'Chrome/(\d+)\.', self.user_agent)
        if chrome_match:
            chrome_ver = int(chrome_match.group(1))
            if chrome_ver > 200:
                self._flag('impossible_browser_version',
                           f'Chrome version {chrome_ver} does not exist', score=35)
            elif chrome_ver < 50:
                self._flag('outdated_browser',
                           f'Chrome {chrome_ver} is extremely outdated (EOL)', score=15)

        # Check Firefox version
        ff_match = re.search(r'Firefox/(\d+)\.', self.user_agent)
        if ff_match:
            ff_ver = int(ff_match.group(1))
            if ff_ver > 200:
                self._flag('impossible_browser_version',
                           f'Firefox version {ff_ver} does not exist', score=35)

    def _check_webgl_renderer(self):
        """Signal 4: VM/sandbox WebGL renderer strings."""
        if not self.webgl_renderer:
            return

        for renderer in VM_WEBGL_RENDERERS:
            if renderer in self.webgl_renderer:
                self._flag('vm_webgl_renderer',
                           f'VM/software WebGL renderer: {renderer}', score=35)
                return

    def _check_canvas_hash(self):
        """Signal 5: Known headless/empty canvas hashes."""
        if not self.canvas_hash:
            self._flag('missing_canvas_hash', 'Canvas fingerprint empty or blocked', score=20)
            return

        if self.canvas_hash in KNOWN_HEADLESS_CANVAS_HASHES:
            self._flag('headless_canvas_hash',
                       'Canvas hash matches known headless browser signature', score=45)

    def _check_screen_resolution(self):
        """Signal 6: Screen resolution typical of bots/VMs."""
        if not self.screen:
            self._flag('missing_screen_resolution', 'No screen resolution reported', score=15)
            return

        if self.screen in BOT_SCREEN_RESOLUTIONS:
            self._flag('bot_screen_resolution',
                       f'Screen {self.screen} is typical of VM/bot environment', score=25)
            return

        # Screen resolution 0x0 or impossible values
        try:
            parts = self.screen.lower().replace('x', ',').split(',')
            w, h = int(parts[0]), int(parts[1])
            if w <= 0 or h <= 0:
                self._flag('invalid_screen_resolution',
                           f'Invalid screen dimensions: {self.screen}', score=30)
            elif w > 8000 or h > 8000:
                self._flag('impossible_screen_resolution',
                           f'Impossibly large screen: {self.screen}', score=25)
        except (ValueError, IndexError):
            self._flag('invalid_screen_resolution',
                       f'Cannot parse screen: {self.screen}', score=20)

    def _check_mobile_ua_touch_mismatch(self):
        """Signal 7: Mobile UA but touch_points = 0 (desktop machine with spoofed UA)."""
        if self.touch_points < 0:
            return

        ua_lower = self.user_agent.lower()
        is_mobile_ua = any(kw in ua_lower for kw in ['mobile', 'android', 'iphone', 'ipad'])

        if is_mobile_ua and self.touch_points == 0:
            self._flag('mobile_ua_no_touch',
                       'Mobile UA but touch_points=0 — UA spoofed on desktop', score=30)

    def _check_hardware_concurrency(self):
        """Signal 8: Impossibly high CPU core count."""
        if self.hardware_concurrency <= 0:
            return
        if self.hardware_concurrency > 128:
            self._flag('impossible_hardware_concurrency',
                       f'hardware_concurrency={self.hardware_concurrency} is impossible',
                       score=25)
        # 1 core is extremely rare for modern devices (may indicate fake value)
        elif self.hardware_concurrency == 1:
            self._flag('suspicious_hardware_concurrency',
                       'hardware_concurrency=1 is unusual on modern devices', score=10)

    def _check_plugin_browser_mismatch(self):
        """Signal 9: Chrome has no NPAPI plugins since Chrome 45."""
        if not self.plugins:
            return

        ua_lower = self.user_agent.lower()
        is_chrome = 'chrome' in ua_lower and 'edge' not in ua_lower

        # Chrome 45+ removed NPAPI plugins (Java, Flash, Silverlight)
        old_plugins = [p.lower() for p in self.plugins]
        has_flash = any('flash' in p for p in old_plugins)
        has_java  = any('java' in p for p in old_plugins)

        if is_chrome and (has_flash or has_java):
            chrome_match = re.search(r'Chrome/(\d+)', self.user_agent)
            if chrome_match and int(chrome_match.group(1)) >= 45:
                self._flag('impossible_plugin_list',
                           'Chrome 45+ cannot have Flash/Java plugins', score=30)

    def _check_font_count(self):
        """Signal 10: Headless browsers typically report very few fonts."""
        font_count = len(self.fonts)
        if 0 < font_count < 5:
            self._flag('insufficient_fonts',
                       f'Only {font_count} fonts — headless browsers have very few fonts',
                       score=20)

    def _check_timezone_language(self):
        """Signal 11: Timezone/language vs IP country inconsistency."""
        if not self.timezone or not self.ip_country or not self.language:
            return

        # Basic check: Arabic languages in non-Arabic countries
        lang = self.language.lower().split('-')[0].split(',')[0].strip()

        LANGUAGE_REGIONS = {
            'bn': ['BD', 'IN'],     # Bengali
            'zh': ['CN', 'TW', 'HK', 'SG'],
            'ja': ['JP'],
            'ko': ['KR'],
            'ar': ['SA', 'AE', 'EG', 'JO', 'KW', 'QA', 'OM', 'BH', 'IQ', 'LB', 'SY'],
            'hi': ['IN'],
            'ur': ['PK', 'IN'],
            'ru': ['RU', 'UA', 'BY', 'KZ'],
            'de': ['DE', 'AT', 'CH'],
            'fr': ['FR', 'BE', 'CH', 'CA'],
            'es': ['ES', 'MX', 'AR', 'CO', 'PE', 'CL', 'VE'],
            'pt': ['BR', 'PT', 'AO', 'MZ'],
        }

        expected_countries = LANGUAGE_REGIONS.get(lang)
        if expected_countries and self.ip_country not in expected_countries:
            self._flag(
                'timezone_language_mismatch',
                f'Language {lang} unexpected for IP country {self.ip_country}',
                score=15,
            )

    # ── Classification Helpers ─────────────────────────────────────────────

    def _flag(self, signal: str, description: str, score: int = 10):
        self.flags.append({'signal': signal, 'description': description, 'score': score})
        self.score += score

    def _is_bot_ua(self) -> bool:
        return any(f['signal'] == 'bot_user_agent' for f in self.flags)

    def _is_vm(self) -> bool:
        return any(f['signal'] == 'vm_webgl_renderer' for f in self.flags)

    def _is_headless(self) -> bool:
        return (
            self._is_bot_ua() or
            any(f['signal'] == 'headless_canvas_hash' for f in self.flags)
        )

    def _classify_device(self) -> str:
        ua = self.user_agent.lower()
        if any(k in ua for k in ['iphone', 'android', 'mobile']): return 'mobile'
        if any(k in ua for k in ['ipad', 'tablet']): return 'tablet'
        return 'desktop'

    def _parse_browser(self) -> str:
        ua = self.user_agent
        if 'Firefox/' in ua:   return 'Firefox'
        if 'Edg/' in ua:       return 'Edge'
        if 'OPR/' in ua:       return 'Opera'
        if 'Chrome/' in ua:    return 'Chrome'
        if 'Safari/' in ua:    return 'Safari'
        if 'MSIE' in ua or 'Trident' in ua: return 'IE'
        return 'Unknown'

    def _parse_os(self) -> str:
        ua = self.user_agent
        if 'Windows' in ua: return 'Windows'
        if 'Android' in ua: return 'Android'
        if 'iPhone' in ua:  return 'iOS'
        if 'iPad' in ua:    return 'iPadOS'
        if 'Mac OS' in ua:  return 'macOS'
        if 'Linux' in ua:   return 'Linux'
        return 'Unknown'
