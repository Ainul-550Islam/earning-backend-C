# =============================================================================
# api/promotions/security_vault/anti_bot_challenge.py
# CAPTCHA, Bot Detection, Behavioral Analysis, Rate Limiting
# =============================================================================

import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied, Throttled

logger = logging.getLogger('security_vault.anti_bot')


# =============================================================================
# ── CONFIG ────────────────────────────────────────────────────────────────────
# =============================================================================

# settings.py তে define করুন:
# RECAPTCHA_SECRET_KEY  = env('RECAPTCHA_SECRET_KEY')
# HCAPTCHA_SECRET_KEY   = env('HCAPTCHA_SECRET_KEY')
# TURNSTILE_SECRET_KEY  = env('TURNSTILE_SECRET_KEY')  # Cloudflare

BOT_SCORE_THRESHOLD     = getattr(settings, 'BOT_SCORE_THRESHOLD', 0.5)  # 0=human, 1=bot
CACHE_PREFIX_BOT        = 'bot:score:{}'
CACHE_PREFIX_VELOCITY   = 'bot:velocity:{}:{}'
CACHE_PREFIX_CHALLENGE  = 'bot:challenge:{}'
CACHE_TTL_BOT_SCORE     = 3600   # 1 hour
CACHE_TTL_VELOCITY      = 60     # 1 minute


# =============================================================================
# ── DATA CLASSES ──────────────────────────────────────────────────────────────
# =============================================================================

@dataclass
class BotAnalysisResult:
    """Bot analysis এর ফলাফল।"""
    is_bot:          bool          = False
    bot_score:       float         = 0.0      # 0.0 = definitely human, 1.0 = definitely bot
    signals:         list          = field(default_factory=list)
    recommended_action: str        = 'allow'  # allow | challenge | block
    reason:          str           = ''

    @property
    def risk_level(self) -> str:
        if self.bot_score < 0.3:
            return 'low'
        elif self.bot_score < 0.6:
            return 'medium'
        elif self.bot_score < 0.85:
            return 'high'
        return 'critical'


@dataclass
class VelocityResult:
    """Request velocity এর ফলাফল।"""
    is_suspicious: bool  = False
    requests_count: int  = 0
    window_seconds: int  = 60
    threshold:      int  = 30
    excess_count:   int  = 0


# =============================================================================
# ── CAPTCHA VERIFIER ──────────────────────────────────────────────────────────
# =============================================================================

class CaptchaVerifier:
    """
    Multiple CAPTCHA provider support — reCAPTCHA v3, hCaptcha, Cloudflare Turnstile।
    """

    class Provider:
        RECAPTCHA_V3 = 'recaptcha_v3'
        HCAPTCHA     = 'hcaptcha'
        TURNSTILE    = 'turnstile'

    VERIFY_URLS = {
        Provider.RECAPTCHA_V3: 'https://www.google.com/recaptcha/api/siteverify',
        Provider.HCAPTCHA:     'https://hcaptcha.com/siteverify',
        Provider.TURNSTILE:    'https://challenges.cloudflare.com/turnstile/v0/siteverify',
    }

    def __init__(self, provider: str = None):
        self.provider = provider or getattr(settings, 'CAPTCHA_PROVIDER', self.Provider.RECAPTCHA_V3)

    def verify(self, token: str, remote_ip: str = None) -> dict:
        """
        CAPTCHA token verify করে।

        Returns:
            dict: {success, score, action, error_codes}
        """
        if not token:
            return {'success': False, 'score': 0.0, 'error_codes': ['missing-input-response']}

        secret = self._get_secret()
        if not secret:
            logger.warning('CAPTCHA secret key not configured — skipping verification.')
            return {'success': True, 'score': 1.0, 'warning': 'captcha_not_configured'}

        import requests
        try:
            payload = {'secret': secret, 'response': token}
            if remote_ip:
                payload['remoteip'] = remote_ip

            response = requests.post(
                self.VERIFY_URLS[self.provider],
                data=payload,
                timeout=5,
            )
            response.raise_for_status()
            result = response.json()

            # Score normalize করো (reCAPTCHA v3: 0-1, hCaptcha: pass/fail)
            if self.provider == self.Provider.RECAPTCHA_V3:
                score = result.get('score', 0.0)
            elif result.get('success'):
                score = 1.0
            else:
                score = 0.0

            logger.info(
                f'CAPTCHA verification: provider={self.provider}, '
                f'success={result.get("success")}, score={score}'
            )
            return {**result, 'score': score, 'provider': self.provider}

        except requests.RequestException as e:
            logger.error(f'CAPTCHA verification request failed: {e}')
            # Fail open — CAPTCHA server down হলে allow করো (production policy অনুযায়ী পরিবর্তন করুন)
            return {'success': True, 'score': 0.5, 'error_codes': ['network-error'], 'fail_open': True}

    def is_human(self, token: str, remote_ip: str = None, min_score: float = 0.5) -> bool:
        """Human কিনা simple boolean check।"""
        result = self.verify(token, remote_ip)
        if not result.get('success'):
            return False
        return result.get('score', 0.0) >= min_score

    def _get_secret(self) -> Optional[str]:
        secrets_map = {
            self.Provider.RECAPTCHA_V3: getattr(settings, 'RECAPTCHA_SECRET_KEY', None),
            self.Provider.HCAPTCHA:     getattr(settings, 'HCAPTCHA_SECRET_KEY', None),
            self.Provider.TURNSTILE:    getattr(settings, 'TURNSTILE_SECRET_KEY', None),
        }
        return secrets_map.get(self.provider)


# =============================================================================
# ── BEHAVIORAL BOT DETECTION ──────────────────────────────────────────────────
# =============================================================================

class BehavioralBotDetector:
    """
    HTTP request এর behavioral signals দেখে bot সনাক্ত করে।
    Machine learning এর বদলে rule-based — fast ও lightweight।
    """

    # Known bad/headless browser User-Agents
    HEADLESS_UA_PATTERNS = [
        r'HeadlessChrome',
        r'PhantomJS',
        r'Selenium',
        r'webdriver',
        r'python-requests',
        r'Go-http-client',
        r'curl/',
        r'wget/',
        r'scrapy',
        r'axios/',
        r'node-fetch',
    ]

    # Legitimate mobile User-Agents কে false positive থেকে বাঁচাতে
    LEGITIMATE_MOBILE_UA_PATTERNS = [
        r'Mozilla/5\.0.*Android',
        r'Mozilla/5\.0.*iPhone',
        r'Mozilla/5\.0.*iPad',
    ]

    def analyze_request(self, request) -> BotAnalysisResult:
        """
        Request analyze করে bot score বের করে।
        সব signal মিলিয়ে final score দেয়।
        """
        result  = BotAnalysisResult()
        signals = []
        score   = 0.0

        user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip_address = self._get_ip(request)

        # ── Signal 1: User-Agent analysis ─────────────────────────────────
        ua_score, ua_signal = self._analyze_user_agent(user_agent)
        score  += ua_score
        if ua_signal:
            signals.append(ua_signal)

        # ── Signal 2: Missing expected browser headers ────────────────────
        missing_score, missing_signals = self._check_missing_browser_headers(request)
        score  += missing_score
        signals.extend(missing_signals)

        # ── Signal 3: Request velocity ────────────────────────────────────
        if ip_address:
            velocity = self.check_velocity(ip_address, window_seconds=60, threshold=30)
            if velocity.is_suspicious:
                score += 0.3
                signals.append(f'high_velocity:{velocity.requests_count}/min')

        # ── Signal 4: Suspicious Accept headers ──────────────────────────
        accept = request.META.get('HTTP_ACCEPT', '')
        if not accept or accept == '*/*':
            score += 0.15
            signals.append('missing_or_wildcard_accept')

        # ── Signal 5: No referer on form submissions ──────────────────────
        if request.method in ('POST', 'PUT') and not request.META.get('HTTP_REFERER'):
            score += 0.10
            signals.append('no_referer_on_mutation')

        # ── Signal 6: Timezone/Language inconsistency ─────────────────────
        tz_header = request.META.get('HTTP_X_TIMEZONE', '')
        lang      = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if request.method == 'POST' and not lang:
            score += 0.10
            signals.append('missing_accept_language')

        # ── Score cap ─────────────────────────────────────────────────────
        score = min(score, 1.0)

        result.bot_score = round(score, 3)
        result.signals   = signals
        result.is_bot    = score >= BOT_SCORE_THRESHOLD

        if score >= 0.85:
            result.recommended_action = 'block'
            result.reason = 'High confidence bot detected.'
        elif score >= 0.5:
            result.recommended_action = 'challenge'
            result.reason = 'Suspicious behavior — CAPTCHA required.'
        else:
            result.recommended_action = 'allow'

        if result.is_bot:
            logger.warning(
                f'Bot detected: ip={ip_address}, score={score:.3f}, '
                f'signals={signals}, action={result.recommended_action}'
            )

        return result

    def check_velocity(
        self,
        identifier: str,
        window_seconds: int = 60,
        threshold: int = 30,
    ) -> VelocityResult:
        """
        Sliding window দিয়ে request velocity check করে।
        identifier হতে পারে IP, user_id, device fingerprint।
        """
        cache_key = CACHE_PREFIX_VELOCITY.format(identifier, window_seconds)
        current   = cache.get(cache_key, 0)
        count     = current + 1
        cache.set(cache_key, count, timeout=window_seconds)

        return VelocityResult(
            is_suspicious = count > threshold,
            requests_count = count,
            window_seconds = window_seconds,
            threshold      = threshold,
            excess_count   = max(0, count - threshold),
        )

    def _analyze_user_agent(self, user_agent: str) -> tuple[float, Optional[str]]:
        """User-Agent analyze করে।"""
        if not user_agent:
            return 0.5, 'missing_user_agent'

        # Headless browser / scripting tool check
        for pattern in self.HEADLESS_UA_PATTERNS:
            if re.search(pattern, user_agent, re.IGNORECASE):
                return 0.8, f'headless_ua:{pattern}'

        # Legitimate mobile browser — false positive prevention
        for pattern in self.LEGITIMATE_MOBILE_UA_PATTERNS:
            if re.search(pattern, user_agent):
                return 0.0, None

        # Very short UA (likely custom/fake)
        if len(user_agent) < 30:
            return 0.3, 'suspiciously_short_ua'

        return 0.0, None

    def _check_missing_browser_headers(self, request) -> tuple[float, list]:
        """Real browser এ থাকার কথা এমন headers check করে।"""
        score   = 0.0
        signals = []

        expected_headers = [
            'HTTP_ACCEPT_ENCODING',
            'HTTP_ACCEPT_LANGUAGE',
            'HTTP_CONNECTION',
        ]

        missing = [h for h in expected_headers if not request.META.get(h)]
        if missing:
            score   = len(missing) * 0.10
            signals = [f'missing_header:{h.replace("HTTP_", "").lower()}' for h in missing]

        return score, signals

    @staticmethod
    def _get_ip(request) -> Optional[str]:
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# =============================================================================
# ── PROOF OF WORK CHALLENGE ────────────────────────────────────────────────────
# =============================================================================

class ProofOfWorkChallenge:
    """
    Client-side Proof of Work — CAPTCHA ছাড়াই bot slow করে।
    Client কে একটি math puzzle solve করতে হয় — bot এর জন্য cost বাড়ে।
    """

    DIFFICULTY = getattr(settings, 'POW_DIFFICULTY', 4)  # leading zeros
    CACHE_TTL  = 300  # 5 minutes

    def generate_challenge(self, session_id: str) -> dict:
        """Client কে solve করার জন্য challenge তৈরি করে।"""
        import secrets
        challenge_id = secrets.token_hex(16)
        prefix       = secrets.token_hex(8)
        target       = '0' * self.DIFFICULTY

        cache.set(
            CACHE_PREFIX_CHALLENGE.format(challenge_id),
            {'prefix': prefix, 'target': target, 'session_id': session_id, 'created_at': time.time()},
            timeout=self.CACHE_TTL,
        )

        return {
            'challenge_id': challenge_id,
            'prefix':       prefix,
            'difficulty':   self.DIFFICULTY,
            'target':       target,
            'algorithm':    'sha256',
            'instruction':  f'Find nonce such that SHA256(prefix + nonce) starts with "{target}"',
        }

    def verify_solution(self, challenge_id: str, nonce: str) -> bool:
        """Client এর solution verify করে।"""
        challenge = cache.get(CACHE_PREFIX_CHALLENGE.format(challenge_id))
        if not challenge:
            logger.warning(f'POW challenge not found or expired: {challenge_id}')
            return False

        # Time check — challenge বেশি পুরনো নয়তো?
        age = time.time() - challenge.get('created_at', 0)
        if age > self.CACHE_TTL:
            return False

        # Solution verify
        test = hashlib.sha256(f"{challenge['prefix']}{nonce}".encode()).hexdigest()
        if test.startswith(challenge['target']):
            # One-time use
            cache.delete(CACHE_PREFIX_CHALLENGE.format(challenge_id))
            return True

        return False


# =============================================================================
# ── DRF PERMISSION: ANTI-BOT ──────────────────────────────────────────────────
# =============================================================================

class AntiBotPermission:
    """
    DRF Permission class হিসেবে ব্যবহার করা যাবে।

    Usage in views:
        permission_classes = [IsAuthenticated, AntiBotPermission]
    """
    message = _('Automated request detected. Please complete the human verification.')

    _detector = BehavioralBotDetector()

    def has_permission(self, request, view) -> bool:
        # Admin bypass
        if request.user and request.user.is_staff:
            return True

        result = self._detector.analyze_request(request)

        # Cache score for this IP to avoid repeated analysis
        ip = self._detector._get_ip(request)
        if ip:
            cache.set(CACHE_PREFIX_BOT.format(ip), result.bot_score, timeout=CACHE_TTL_BOT_SCORE)

        if result.recommended_action == 'block':
            raise PermissionDenied(self.message)

        if result.recommended_action == 'challenge':
            # CAPTCHA token থাকলে verify করো
            captcha_token = request.META.get('HTTP_X_CAPTCHA_TOKEN', '')
            if captcha_token:
                verifier = CaptchaVerifier()
                if not verifier.is_human(captcha_token, self._detector._get_ip(request)):
                    raise PermissionDenied(_('CAPTCHA verification failed.'))
                return True
            # CAPTCHA token নেই — challenge দাও
            raise PermissionDenied({
                'detail': _('Human verification required.'),
                'challenge_required': True,
                'captcha_provider': getattr(settings, 'CAPTCHA_PROVIDER', 'recaptcha_v3'),
            })

        return True


# =============================================================================
# ── HONEYPOT ──────────────────────────────────────────────────────────────────
# =============================================================================

class HoneypotDetector:
    """
    Hidden form field দিয়ে bot ধরে।
    Real user কখনো hidden field fill করে না — bot করে।
    """

    HONEYPOT_FIELD_NAME = getattr(settings, 'HONEYPOT_FIELD_NAME', '_hp_email')

    def check_honeypot(self, request) -> bool:
        """
        Honeypot field filled হলে True (bot) return করে।
        """
        if request.method not in ('POST', 'PUT', 'PATCH'):
            return False

        try:
            import json
            body = json.loads(request.body.decode('utf-8')) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = request.POST.dict()

        honeypot_value = body.get(self.HONEYPOT_FIELD_NAME, None)

        if honeypot_value:  # Hidden field fill হয়েছে — bot!
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            logger.warning(f'Honeypot triggered by IP: {ip}, value: {honeypot_value[:50]}')
            return True

        return False
