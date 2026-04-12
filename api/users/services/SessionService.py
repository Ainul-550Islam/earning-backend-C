# api/users/services/SessionService.py
# ============================================================
# Session Management — Active sessions list + Remote logout
# Redis তে store করা হয়, JWT blacklist এর সাথে কাজ করে
# ============================================================

import json
import uuid
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

SESSION_TTL_DAYS = getattr(settings, 'SESSION_TTL_DAYS', 30)
MAX_SESSIONS_PER_USER = getattr(settings, 'MAX_SESSIONS_PER_USER', 5)


class SessionService:
    """
    User এর সব active session track করো।
    কাজ:
    - Login করলে session create করো
    - User dashboard এ সব active device দেখাও
    - দূর থেকে যেকোনো session logout করো
    - Max session limit enforce করো
    """

    @staticmethod
    def _sessions_key(user_id) -> str:
        return f"user_sessions:{user_id}"

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"session_detail:{session_id}"

    @staticmethod
    def create_session(user, request, refresh_token: str) -> dict:
        """
        Login সফল হলে নতুন session তৈরি করো।
        session_id টা JWT token এর সাথে link করা হয়।
        """
        session_id = str(uuid.uuid4())

        # Device info extract করো
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        ip_address = SessionService._get_client_ip(request)
        device_type = SessionService._parse_device_type(user_agent)

        session_data = {
            'session_id': session_id,
            'user_id': str(user.id),
            'ip_address': ip_address,
            'user_agent': user_agent,
            'device_type': device_type,
            'device_name': SessionService._parse_device_name(user_agent),
            'refresh_token_jti': SessionService._get_token_jti(refresh_token),
            'created_at': timezone.now().isoformat(),
            'last_active': timezone.now().isoformat(),
            'is_current': True,
        }

        # Individual session store করো
        ttl = SESSION_TTL_DAYS * 24 * 3600
        cache.set(SessionService._session_key(session_id), json.dumps(session_data), timeout=ttl)

        # User এর session list এ add করো
        sessions_key = SessionService._sessions_key(user.id)
        raw = cache.get(sessions_key)
        session_ids = json.loads(raw) if raw else []

        # Max session limit — পুরনো session remove করো
        if len(session_ids) >= MAX_SESSIONS_PER_USER:
            oldest = session_ids.pop(0)
            cache.delete(SessionService._session_key(oldest))
            logger.info(f"Max session limit reached for user {user.id}, removed oldest session")

        session_ids.append(session_id)
        cache.set(sessions_key, json.dumps(session_ids), timeout=ttl)

        logger.info(f"Session created for user {user.id} from {ip_address}")
        return {'session_id': session_id, **session_data}

    @staticmethod
    def get_active_sessions(user) -> list:
        """User এর সব active session list করো"""
        sessions_key = SessionService._sessions_key(user.id)
        raw = cache.get(sessions_key)
        if not raw:
            return []

        session_ids = json.loads(raw)
        sessions = []
        valid_ids = []

        for sid in session_ids:
            raw_session = cache.get(SessionService._session_key(sid))
            if raw_session:
                session = json.loads(raw_session)
                # Password hide করো, sensitive info remove করো
                session.pop('refresh_token_jti', None)
                sessions.append(session)
                valid_ids.append(sid)

        # Clean up expired sessions
        if len(valid_ids) != len(session_ids):
            ttl = SESSION_TTL_DAYS * 24 * 3600
            cache.set(sessions_key, json.dumps(valid_ids), timeout=ttl)

        return sessions

    @staticmethod
    def revoke_session(user, session_id: str, current_session_id: str = None) -> dict:
        """
        নির্দিষ্ট একটা session logout করো (remote logout)।
        current_session_id দিলে নিজের session revoke করা block করা হয়।
        """
        if session_id == current_session_id:
            return {'success': False, 'error': 'নিজের current session revoke করা যাবে না। Logout ব্যবহার করুন।'}

        raw_session = cache.get(SessionService._session_key(session_id))
        if not raw_session:
            return {'success': False, 'error': 'Session পাওয়া যায়নি বা expired।'}

        session = json.loads(raw_session)

        # Verify করো এই session ওই user এর
        if str(session.get('user_id')) != str(user.id):
            logger.warning(f"User {user.id} tried to revoke session of another user")
            return {'success': False, 'error': 'Unauthorized।'}

        # JWT token blacklist করো
        jti = session.get('refresh_token_jti')
        if jti:
            SessionService._blacklist_token_jti(jti)

        # Cache থেকে delete করো
        cache.delete(SessionService._session_key(session_id))

        # Session list থেকে remove করো
        sessions_key = SessionService._sessions_key(user.id)
        raw = cache.get(sessions_key)
        if raw:
            ids = json.loads(raw)
            if session_id in ids:
                ids.remove(session_id)
                cache.set(sessions_key, json.dumps(ids), timeout=SESSION_TTL_DAYS * 24 * 3600)

        logger.info(f"Session {session_id} revoked for user {user.id}")
        return {'success': True, 'message': 'Device logout করা হয়েছে।'}

    @staticmethod
    def revoke_all_sessions(user, except_session_id: str = None) -> dict:
        """
        সব session logout করো (except current)।
        Security breach মনে হলে user এই feature use করবে।
        """
        sessions_key = SessionService._sessions_key(user.id)
        raw = cache.get(sessions_key)
        if not raw:
            return {'success': True, 'revoked': 0}

        session_ids = json.loads(raw)
        revoked = 0
        remaining = []

        for sid in session_ids:
            if sid == except_session_id:
                remaining.append(sid)
                continue

            raw_session = cache.get(SessionService._session_key(sid))
            if raw_session:
                session = json.loads(raw_session)
                jti = session.get('refresh_token_jti')
                if jti:
                    SessionService._blacklist_token_jti(jti)
                cache.delete(SessionService._session_key(sid))
                revoked += 1

        cache.set(sessions_key, json.dumps(remaining), timeout=SESSION_TTL_DAYS * 24 * 3600)
        logger.info(f"Revoked {revoked} sessions for user {user.id}")
        return {'success': True, 'revoked': revoked, 'message': f'{revoked}টি device logout করা হয়েছে।'}

    @staticmethod
    def update_last_active(session_id: str):
        """প্রতিটি API call এ last_active update করো"""
        raw = cache.get(SessionService._session_key(session_id))
        if raw:
            session = json.loads(raw)
            session['last_active'] = timezone.now().isoformat()
            session['is_current'] = True
            # TTL reset করো
            ttl = SESSION_TTL_DAYS * 24 * 3600
            cache.set(SessionService._session_key(session_id), json.dumps(session), timeout=ttl)

    @staticmethod
    def _get_client_ip(request) -> str:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    @staticmethod
    def _parse_device_type(user_agent: str) -> str:
        ua = user_agent.lower()
        if any(x in ua for x in ['mobile', 'android', 'iphone']):
            return 'Mobile'
        if 'tablet' in ua or 'ipad' in ua:
            return 'Tablet'
        return 'Desktop'

    @staticmethod
    def _parse_device_name(user_agent: str) -> str:
        ua = user_agent.lower()
        if 'chrome' in ua:
            return 'Chrome Browser'
        if 'firefox' in ua:
            return 'Firefox Browser'
        if 'safari' in ua:
            return 'Safari Browser'
        if 'android' in ua:
            return 'Android Device'
        if 'iphone' in ua:
            return 'iPhone'
        return 'Unknown Device'

    @staticmethod
    def _get_token_jti(refresh_token: str) -> str:
        """JWT refresh token থেকে JTI extract করো"""
        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            token = RefreshToken(refresh_token)
            return str(token.get('jti', ''))
        except Exception:
            return ''

    @staticmethod
    def _blacklist_token_jti(jti: str):
        """Token JTI blacklist করো"""
        try:
            from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
            token = OutstandingToken.objects.filter(jti=jti).first()
            if token:
                BlacklistedToken.objects.get_or_create(token=token)
        except Exception as e:
            logger.warning(f"Token blacklist error (JTI: {jti}): {e}")