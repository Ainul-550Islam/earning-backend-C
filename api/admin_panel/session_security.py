# api/admin_panel/session_security.py
"""
Admin Session Security — hijacking detection, concurrent session limits,
device fingerprinting, anomalous behaviour detection.
"""
from __future__ import annotations
import hashlib
import logging
from typing import Optional, Tuple
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_CONCURRENT_SESSIONS = 3  # Per admin user
SESSION_FINGERPRINT_FIELDS = ['HTTP_USER_AGENT', 'HTTP_ACCEPT_LANGUAGE', 'REMOTE_ADDR']


class SessionSecurityService:
    """Admin session security checks."""

    @classmethod
    def fingerprint_request(cls, request) -> str:
        """Generate session fingerprint from request metadata."""
        parts = [
            request.META.get('HTTP_USER_AGENT', ''),
            request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            request.META.get('REMOTE_ADDR', ''),
        ]
        raw = '|'.join(parts)
        return hashlib.md5(raw.encode()).hexdigest()

    @classmethod
    def bind_session_fingerprint(cls, request) -> None:
        """Bind fingerprint to current session."""
        if not request.user.is_authenticated:
            return
        fp = cls.fingerprint_request(request)
        request.session['_admin_fingerprint'] = fp
        request.session['_admin_ip'] = request.META.get('REMOTE_ADDR', '')
        request.session['_admin_user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:200]

    @classmethod
    def check_session_integrity(cls, request) -> Tuple[bool, str]:
        """
        Check if session has been hijacked.
        Returns (is_valid, reason).
        """
        if not request.user.is_authenticated:
            return True, 'not_authenticated'

        stored_fp = request.session.get('_admin_fingerprint')
        if not stored_fp:
            return True, 'no_fingerprint'

        current_fp = cls.fingerprint_request(request)
        if stored_fp != current_fp:
            stored_ip = request.session.get('_admin_ip', '')
            current_ip = request.META.get('REMOTE_ADDR', '')
            if stored_ip != current_ip:
                logger.warning(
                    f"[SessionSecurity] IP change detected for {request.user.username}: "
                    f"{stored_ip} -> {current_ip}"
                )
                from api.admin_panel.signals_kb import admin_session_hijack_risk, fire_kb_signal
                fire_kb_signal(admin_session_hijack_risk, user_id=request.user.pk,
                               session_key=request.session.session_key, risk_level='high')
                return False, f'Session IP changed: {stored_ip} -> {current_ip}'
        return True, 'ok'

    @classmethod
    def enforce_concurrent_limit(cls, user) -> Tuple[bool, int]:
        """
        Check and enforce concurrent session limit.
        Returns (allowed, active_count).
        """
        try:
            from api.admin_panel.models.activity import AdminSession
            active = AdminSession.objects.filter(user=user, is_active=True).count()
            return active < MAX_CONCURRENT_SESSIONS, active
        except Exception:
            return True, 0

    @classmethod
    def revoke_other_sessions(cls, user, keep_session_key: str) -> int:
        """Revoke all sessions except the current one."""
        try:
            from api.admin_panel.models.activity import AdminSession
            count = AdminSession.objects.filter(
                user=user, is_active=True
            ).exclude(session_key=keep_session_key).update(
                is_active=False, status='force_logout', ended_at=timezone.now()
            )
            return count
        except Exception:
            return 0

    @classmethod
    def detect_brute_force(cls, username: str, ip: str) -> Tuple[bool, int]:
        """
        Track failed login attempts.
        Returns (is_blocked, attempt_count).
        """
        key = f'admin_panel:login_fail:{ip}:{username[:20]}'
        attempts = cache.get(key, 0) + 1
        cache.set(key, attempts, 900)  # 15 min window

        if attempts >= 5:
            from api.admin_panel.signals_kb import admin_brute_force_detected, fire_kb_signal
            fire_kb_signal(admin_brute_force_detected, ip=ip, attempts=attempts, window_seconds=900)
            return True, attempts
        return False, attempts

    @classmethod
    def clear_brute_force_lock(cls, username: str, ip: str) -> None:
        cache.delete(f'admin_panel:login_fail:{ip}:{username[:20]}')

    @classmethod
    def detect_impossible_travel(cls, user, current_ip: str) -> bool:
        """Detect impossible travel (login from different country within minutes)."""
        key = f'admin_panel:last_ip:{user.pk}'
        last_ip = cache.get(key)
        cache.set(key, current_ip, 3600)
        if not last_ip or last_ip == current_ip:
            return False
        # Different IPs — check countries
        try:
            from api.admin_panel.helpers import get_ip_info
            last_info    = get_ip_info(last_ip)
            current_info = get_ip_info(current_ip)
            if last_info.get('country') != current_info.get('country'):
                logger.warning(f"[SessionSecurity] Impossible travel: {user.username} "
                               f"{last_ip}({last_info.get('country')}) -> {current_ip}({current_info.get('country')})")
                return True
        except Exception:
            pass
        return False