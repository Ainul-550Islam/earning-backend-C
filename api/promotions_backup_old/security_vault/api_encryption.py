# =============================================================================
# api/promotions/security_vault/api_encryption.py
# End-to-End API Response Encryption
# Sensitive API response গুলো client এ পাঠানোর আগে encrypt করে
# =============================================================================

import base64
import json
import logging
import os
from typing import Any

from django.conf import settings
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

logger = logging.getLogger('security_vault.api_encryption')


class APIResponseEncryptor:
    """
    API response payload encrypt করে।
    Client একটি public key পাঠায়, server সেটা দিয়ে response encrypt করে।

    Flow:
        1. Client: RSA key pair generate করে, public key পাঠায়
        2. Server: Random AES key generate করে
        3. Server: AES key দিয়ে payload encrypt করে
        4. Server: Client এর RSA public key দিয়ে AES key encrypt করে
        5. Server: {encrypted_key, encrypted_payload} পাঠায়
        6. Client: RSA private key দিয়ে AES key decrypt করে, তারপর payload decrypt করে
    """

    def encrypt_response(self, payload: dict, client_public_key_pem: str) -> dict:
        """Payload RSA+AES hybrid encryption দিয়ে encrypt করে।"""
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            # ── ১. Random AES-256 key ──────────────────────────────────────
            aes_key = os.urandom(32)   # 256-bit
            nonce   = os.urandom(12)   # 96-bit (GCM standard)

            # ── ২. Payload AES-256-GCM দিয়ে encrypt ──────────────────────
            aesgcm    = AESGCM(aes_key)
            plaintext = json.dumps(payload, separators=(',', ':')).encode('utf-8')
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)

            # ── ৩. AES key client এর RSA public key দিয়ে encrypt ─────────
            public_key = serialization.load_pem_public_key(
                client_public_key_pem.encode() if isinstance(client_public_key_pem, str)
                else client_public_key_pem
            )
            encrypted_aes_key = public_key.encrypt(
                aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                )
            )

            return {
                'encrypted':      True,
                'algorithm':      'RSA-OAEP+AES-256-GCM',
                'encrypted_key':  base64.b64encode(encrypted_aes_key).decode(),
                'nonce':          base64.b64encode(nonce).decode(),
                'ciphertext':     base64.b64encode(ciphertext).decode(),
            }

        except ImportError:
            logger.warning('cryptography package not installed — returning unencrypted.')
            return {'encrypted': False, 'data': payload}
        except Exception as e:
            logger.exception(f'API response encryption failed: {e}')
            return {'encrypted': False, 'data': payload, 'error': 'encryption_failed'}

    def decrypt_request(self, encrypted_body: dict, server_private_key_pem: str) -> dict:
        """Client থেকে আসা encrypted request body decrypt করে।"""
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            encrypted_key = base64.b64decode(encrypted_body['encrypted_key'])
            nonce         = base64.b64decode(encrypted_body['nonce'])
            ciphertext    = base64.b64decode(encrypted_body['ciphertext'])

            private_key = serialization.load_pem_private_key(
                server_private_key_pem.encode() if isinstance(server_private_key_pem, str)
                else server_private_key_pem,
                password=None,
            )
            aes_key = private_key.decrypt(
                encrypted_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                )
            )

            aesgcm    = AESGCM(aes_key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext.decode('utf-8'))

        except Exception as e:
            logger.exception(f'Request decryption failed: {e}')
            raise ValueError('Request decryption failed.')


class EncryptedResponseRenderer(JSONRenderer):
    """
    DRF Renderer — sensitive endpoint এর response automatically encrypt করে।

    Usage in view:
        class SensitiveDataView(APIView):
            renderer_classes = [EncryptedResponseRenderer]
    """
    media_type = 'application/vnd.api+encrypted'
    format     = 'encrypted_json'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        request = renderer_context.get('request') if renderer_context else None

        # Client এর public key header থেকে নাও
        client_pub_key = None
        if request:
            client_pub_key = request.META.get('HTTP_X_CLIENT_PUBLIC_KEY', '')

        if not client_pub_key:
            # No public key — plain JSON fallback
            logger.warning('No client public key provided — returning unencrypted response.')
            return super().render(data, accepted_media_type, renderer_context)

        encryptor      = APIResponseEncryptor()
        encrypted_data = encryptor.encrypt_response(data, client_pub_key)
        return super().render(encrypted_data, accepted_media_type, renderer_context)


# =============================================================================
# api/promotions/security_vault/jwt_manager.py
# JWT Token Management — Custom claims, rotation, blacklisting
# =============================================================================

import logging
import uuid
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger('security_vault.jwt_manager')

# JWT config
ACCESS_TOKEN_LIFETIME  = getattr(settings, 'JWT_ACCESS_TOKEN_LIFETIME',  timedelta(minutes=30))
REFRESH_TOKEN_LIFETIME = getattr(settings, 'JWT_REFRESH_TOKEN_LIFETIME', timedelta(days=7))
CACHE_PREFIX_BLACKLIST = 'jwt:blacklist:{}'
CACHE_PREFIX_REFRESH   = 'jwt:refresh:{}'


class JWTManager:
    """
    JWT token lifecycle management।
    djangorestframework-simplejwt এর সাথে compatible।

    Features:
    - Custom claims (user_level, trust_score, country)
    - Token blacklisting (logout)
    - Refresh token rotation
    - Suspicious login detection
    """

    def generate_token_pair(self, user) -> dict:
        """
        Access + Refresh token pair তৈরি করে।
        djangorestframework-simplejwt ব্যবহার করলে এটি extend করুন।
        """
        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(user)

            # ── Custom claims যোগ করো ────────────────────────────────────
            refresh['user_id']     = user.pk
            refresh['username']    = user.username
            refresh['is_staff']    = user.is_staff
            refresh['is_advertiser'] = getattr(user, 'is_advertiser', False)
            refresh['jti_family']  = str(uuid.uuid4())  # Refresh token rotation tracking

            # Reputation থেকে trust score ও level নাও
            try:
                from api.promotions.models import UserReputation
                rep = UserReputation.objects.get(user=user)
                refresh['trust_score'] = rep.trust_score
                refresh['user_level']  = rep.level
            except Exception:
                refresh['trust_score'] = 50
                refresh['user_level']  = 1

            # Country code
            try:
                refresh['country'] = getattr(getattr(user, 'profile', None), 'country_code', 'XX')
            except Exception:
                refresh['country'] = 'XX'

            access = refresh.access_token
            # Access token এ অতিরিক্ত claims
            access['session_id'] = str(uuid.uuid4())

            return {
                'access':              str(access),
                'refresh':             str(refresh),
                'access_expires_in':   int(ACCESS_TOKEN_LIFETIME.total_seconds()),
                'refresh_expires_in':  int(REFRESH_TOKEN_LIFETIME.total_seconds()),
                'token_type':          'Bearer',
            }

        except ImportError:
            raise ImproperlyConfigured(
                'djangorestframework-simplejwt required. '
                'Install: pip install djangorestframework-simplejwt'
            )

    def blacklist_token(self, token_jti: str, expiry_seconds: int = None) -> None:
        """Token blacklist করে (logout এর সময়)।"""
        ttl = expiry_seconds or int(REFRESH_TOKEN_LIFETIME.total_seconds())
        cache.set(CACHE_PREFIX_BLACKLIST.format(token_jti), True, timeout=ttl)
        logger.info(f'JWT token blacklisted: jti={token_jti}')

    def is_blacklisted(self, token_jti: str) -> bool:
        """Token blacklisted কিনা check করে।"""
        return bool(cache.get(CACHE_PREFIX_BLACKLIST.format(token_jti)))

    def rotate_refresh_token(self, old_refresh_token: str) -> dict:
        """
        Refresh token rotation — পুরনো token blacklist করে নতুন pair দেয়।
        Refresh token theft detect করতে পারে।
        """
        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            from rest_framework_simplejwt.exceptions import TokenError

            old_token = RefreshToken(old_refresh_token)
            jti = str(old_token['jti'])

            # ── Blacklist check ────────────────────────────────────────────
            if self.is_blacklisted(jti):
                # Blacklisted token reuse = token theft!
                logger.critical(
                    f'Refresh token reuse detected (possible theft): jti={jti}. '
                    f'All tokens for user invalidated.'
                )
                # user এর সব token invalidate করো
                user_id = old_token.get('user_id')
                if user_id:
                    self._invalidate_all_user_tokens(user_id)
                raise AuthenticationFailed('Token reuse detected. Please login again.')

            # ── Old token blacklist করো ────────────────────────────────────
            self.blacklist_token(jti)

            # ── নতুন token pair তৈরি করো ──────────────────────────────────
            from django.contrib.auth import get_user_model
            User    = get_user_model()
            user_id = old_token.get('user_id')
            user    = User.objects.get(pk=user_id)
            return self.generate_token_pair(user)

        except Exception as e:
            logger.exception(f'Token rotation failed: {e}')
            raise AuthenticationFailed('Token refresh failed.')

    def detect_suspicious_login(self, user, request) -> dict:
        """
        Login attempt suspicious কিনা detect করে।
        নতুন IP, নতুন device, অস্বাভাবিক সময়ে login।
        """
        ip         = self._get_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        hour       = timezone.now().hour
        signals    = []

        # ── Check 1: Unusual login hour ───────────────────────────────────
        if hour < 5 or hour > 23:
            signals.append('unusual_login_hour')

        # ── Check 2: New IP ────────────────────────────────────────────────
        known_ips_key = f'jwt:known_ips:{user.pk}'
        known_ips     = cache.get(known_ips_key, set())
        if ip and ip not in known_ips:
            signals.append('new_ip_address')
            known_ips.add(ip)
            cache.set(known_ips_key, known_ips, timeout=86400 * 30)  # 30 days

        # ── Check 3: Failed attempts ───────────────────────────────────────
        failed_key   = f'jwt:failed_logins:{ip}'
        failed_count = cache.get(failed_key, 0)
        if failed_count >= 3:
            signals.append(f'recent_failed_attempts:{failed_count}')

        is_suspicious = len(signals) >= 2
        if is_suspicious:
            logger.warning(
                f'Suspicious login for user #{user.pk}: ip={ip}, signals={signals}'
            )

        return {
            'is_suspicious': is_suspicious,
            'signals':       signals,
            'ip':            ip,
        }

    def record_failed_login(self, ip: str) -> int:
        """Failed login attempt record করে।"""
        key   = f'jwt:failed_logins:{ip}'
        count = cache.get(key, 0) + 1
        cache.set(key, count, timeout=3600)  # 1 hour
        if count >= 10:
            logger.warning(f'Brute force attack detected from IP: {ip} ({count} failures)')
        return count

    def _invalidate_all_user_tokens(self, user_id: int) -> None:
        """User এর সব active tokens invalidate করে।"""
        # এই implementation Django আপনার user session বা token store অনুযায়ী পরিবর্তন করুন
        invalidation_key = f'jwt:user_invalidated:{user_id}'
        cache.set(invalidation_key, int(timezone.now().timestamp()), timeout=86400 * 7)
        logger.info(f'All tokens invalidated for user #{user_id}')

    @staticmethod
    def _get_ip(request) -> Optional[str]:
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# =============================================================================
# api/promotions/security_vault/ip_whitelist.py
# IP Whitelist — শুধু নির্দিষ্ট IP থেকে sensitive API access
# =============================================================================

import ipaddress
import logging
from typing import Union

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

logger = logging.getLogger('security_vault.ip_whitelist')

CACHE_KEY_WHITELIST = 'security:ip_whitelist'
CACHE_TTL_WHITELIST = 300  # 5 minutes


class IPWhitelistManager:
    """
    IP Whitelist management।
    settings.py অথবা DB থেকে whitelist নিতে পারে।

    settings.py তে:
        ADMIN_IP_WHITELIST = ['192.168.1.0/24', '10.0.0.1', '203.0.113.5']
    """

    def __init__(self, whitelist: list = None):
        self._static_whitelist = whitelist or getattr(settings, 'ADMIN_IP_WHITELIST', [])

    def is_allowed(self, ip: str) -> bool:
        """IP address allowed কিনা check করে।"""
        if not ip:
            return False

        # Whitelist empty হলে সব allow করো (optional — আপনার policy অনুযায়ী)
        if not self._static_whitelist:
            return True

        try:
            client_ip = ipaddress.ip_address(ip.strip())
        except ValueError:
            logger.warning(f'Invalid IP address format: {ip}')
            return False

        for entry in self._get_effective_whitelist():
            try:
                if '/' in entry:
                    # CIDR range check
                    if client_ip in ipaddress.ip_network(entry, strict=False):
                        return True
                else:
                    # Exact IP check
                    if client_ip == ipaddress.ip_address(entry):
                        return True
            except ValueError:
                logger.warning(f'Invalid whitelist entry: {entry}')
                continue

        logger.warning(f'IP not in whitelist: {ip}')
        return False

    def _get_effective_whitelist(self) -> list:
        """Static list + DB/cache whitelist combine করে।"""
        cached = cache.get(CACHE_KEY_WHITELIST)
        if cached:
            return self._static_whitelist + cached

        # DB থেকে dynamic whitelist (optional)
        db_whitelist = self._load_from_db()
        if db_whitelist:
            cache.set(CACHE_KEY_WHITELIST, db_whitelist, timeout=CACHE_TTL_WHITELIST)

        return self._static_whitelist + (db_whitelist or [])

    @staticmethod
    def _load_from_db() -> list:
        """DB থেকে whitelist load করে (optional)।"""
        try:
            # আপনার IPWhitelist model থাকলে এখানে load করুন
            # from .models import IPWhitelistEntry
            # return list(IPWhitelistEntry.objects.filter(is_active=True).values_list('ip_cidr', flat=True))
            return []
        except Exception:
            return []

    def add_to_whitelist(self, ip_or_cidr: str) -> bool:
        """Runtime এ IP add করে।"""
        try:
            if '/' in ip_or_cidr:
                ipaddress.ip_network(ip_or_cidr, strict=False)
            else:
                ipaddress.ip_address(ip_or_cidr)
            self._static_whitelist.append(ip_or_cidr)
            cache.delete(CACHE_KEY_WHITELIST)
            return True
        except ValueError:
            return False

    def remove_from_whitelist(self, ip_or_cidr: str) -> bool:
        """Whitelist থেকে IP remove করে।"""
        if ip_or_cidr in self._static_whitelist:
            self._static_whitelist.remove(ip_or_cidr)
            cache.delete(CACHE_KEY_WHITELIST)
            return True
        return False


class IPWhitelistPermission(BasePermission):
    """
    DRF Permission — শুধু whitelisted IP থেকে access দেয়।

    Usage:
        class AdminOnlyView(APIView):
            permission_classes = [IsAdminUser, IPWhitelistPermission]
    """
    message = 'Access denied from this IP address.'

    _manager = IPWhitelistManager()

    def has_permission(self, request, view) -> bool:
        ip = self._get_ip(request)
        if not self._manager.is_allowed(ip):
            logger.warning(
                f'IP whitelist blocked: ip={ip}, user={getattr(request.user, "pk", "anon")}, '
                f'path={request.path}'
            )
            raise PermissionDenied(self.message)
        return True

    @staticmethod
    def _get_ip(request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
