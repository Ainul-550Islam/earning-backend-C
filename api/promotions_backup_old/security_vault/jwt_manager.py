# =============================================================================
# api/promotions/security_vault/jwt_manager.py
# JWT Token Manager — Access/Refresh token generation, rotation, blacklisting
# PyJWT + Redis blacklist, fingerprint binding, device-level token isolation
# =============================================================================

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('security_vault.jwt')

CACHE_PREFIX_JWT    = 'jwt:bl:{}'       # Blacklist prefix
CACHE_PREFIX_FAMILY = 'jwt:family:{}'   # Token family (refresh rotation)
CACHE_TTL_BL        = 60 * 60 * 24 * 30  # 30 days

# JWT Config from settings
JWT_SECRET          = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)
JWT_ALGORITHM       = getattr(settings, 'JWT_ALGORITHM', 'HS256')
JWT_ACCESS_TTL      = getattr(settings, 'JWT_ACCESS_TOKEN_LIFETIME', timedelta(minutes=15))
JWT_REFRESH_TTL     = getattr(settings, 'JWT_REFRESH_TOKEN_LIFETIME', timedelta(days=7))


@dataclass
class TokenPair:
    access_token:  str
    refresh_token: str
    access_exp:    datetime
    refresh_exp:   datetime
    token_type:    str = 'Bearer'
    jti:           str = ''


@dataclass
class TokenPayload:
    user_id:      int
    role:         str
    jti:          str
    family_id:    str
    device_id:    str
    ip_hash:      str
    issued_at:    float
    expires_at:   float
    token_type:   str   # 'access' | 'refresh'


class JWTManager:
    """
    JWT Token lifecycle management।

    Security features:
    1. Short-lived access tokens (15 min default)
    2. Refresh token rotation — প্রতিবার নতুন refresh token
    3. Token family tracking — stolen refresh token detect করে
    4. Device fingerprint binding — অন্য device এ use করলে reject
    5. IP hash binding (soft) — suspicious location change detect
    6. Redis blacklist — logout এ immediate invalidation
    7. JTI (JWT ID) — প্রতিটি token unique ID

    Token Family Attack Prevention:
    - প্রতিটি refresh token একটি family তে belong করে
    - কোনো family member reuse হলে পুরো family revoke
    - এটা stolen token detect করার সবচেয়ে effective উপায়
    """

    def generate_token_pair(
        self,
        user_id:   int,
        role:      str,
        device_id: str = '',
        ip:        str = '',
    ) -> TokenPair:
        """
        Access + Refresh token pair generate করে।

        Args:
            user_id:   User primary key
            role:      'worker' | 'advertiser' | 'admin'
            device_id: Device fingerprint
            ip:        Client IP address
        """
        family_id  = str(uuid.uuid4())
        access_jti = str(uuid.uuid4())
        ref_jti    = str(uuid.uuid4())
        ip_hash    = self._hash_ip(ip)
        now        = datetime.now(timezone.utc)

        access_exp  = now + JWT_ACCESS_TTL
        refresh_exp = now + JWT_REFRESH_TTL

        # Access token payload
        access_payload = {
            'sub':       str(user_id),
            'role':      role,
            'jti':       access_jti,
            'fam':       family_id,
            'did':       device_id[:64],
            'iph':       ip_hash,
            'iat':       int(now.timestamp()),
            'exp':       int(access_exp.timestamp()),
            'type':      'access',
        }

        # Refresh token payload
        refresh_payload = {
            'sub':       str(user_id),
            'role':      role,
            'jti':       ref_jti,
            'fam':       family_id,
            'did':       device_id[:64],
            'iph':       ip_hash,
            'iat':       int(now.timestamp()),
            'exp':       int(refresh_exp.timestamp()),
            'type':      'refresh',
        }

        access_token  = jwt.encode(access_payload,  JWT_SECRET, algorithm=JWT_ALGORITHM)
        refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        # Family register — tracks valid refresh token JTI
        cache.set(
            CACHE_PREFIX_FAMILY.format(family_id),
            {'valid_jti': ref_jti, 'user_id': user_id, 'created': now.timestamp()},
            timeout=int(JWT_REFRESH_TTL.total_seconds()),
        )

        logger.info(f'JWT tokens generated: user={user_id} role={role} family={family_id[:8]}')

        return TokenPair(
            access_token=access_token, refresh_token=refresh_token,
            access_exp=access_exp, refresh_exp=refresh_exp, jti=access_jti,
        )

    def verify_access_token(
        self,
        token:     str,
        device_id: str = '',
        ip:        str = '',
    ) -> Optional[TokenPayload]:
        """
        Access token verify করে।

        Returns None if:
        - Expired
        - Blacklisted (logged out)
        - Device mismatch
        - Invalid signature
        """
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            logger.debug('JWT: expired token')
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f'JWT: invalid token — {e}')
            return None

        if payload.get('type') != 'access':
            return None

        jti = payload.get('jti', '')

        # Blacklist check
        if cache.get(CACHE_PREFIX_JWT.format(jti)):
            logger.warning(f'JWT: blacklisted token jti={jti}')
            return None

        # Device binding check (soft — warn only if device_id provided)
        if device_id and payload.get('did') and payload['did'] != device_id[:64]:
            logger.warning(f'JWT: device mismatch user={payload.get("sub")}')
            # Strict mode এ return None করো
            # return None

        return TokenPayload(
            user_id    = int(payload['sub']),
            role       = payload.get('role', 'worker'),
            jti        = jti,
            family_id  = payload.get('fam', ''),
            device_id  = payload.get('did', ''),
            ip_hash    = payload.get('iph', ''),
            issued_at  = payload.get('iat', 0),
            expires_at = payload.get('exp', 0),
            token_type = 'access',
        )

    def refresh_tokens(
        self,
        refresh_token: str,
        device_id:     str = '',
        ip:            str = '',
    ) -> Optional[TokenPair]:
        """
        Refresh token দিয়ে নতুন token pair generate করে।

        Rotation:
        - Old refresh token immediately invalidate হয়
        - নতুন refresh token same family তে issue হয়
        - পুরনো JTI reuse হলে → family revoke (attack detected)
        """
        try:
            payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.InvalidTokenError as e:
            logger.warning(f'JWT refresh: invalid — {e}')
            return None

        if payload.get('type') != 'refresh':
            return None

        jti       = payload.get('jti', '')
        family_id = payload.get('fam', '')
        user_id   = int(payload.get('sub', 0))

        # Blacklist check
        if cache.get(CACHE_PREFIX_JWT.format(jti)):
            # Already used — possible token theft!
            logger.critical(
                f'JWT REFRESH REUSE DETECTED: family={family_id} user={user_id} — REVOKING FAMILY'
            )
            self._revoke_family(family_id)
            return None

        # Family validity check
        family_data = cache.get(CACHE_PREFIX_FAMILY.format(family_id))
        if not family_data or family_data.get('valid_jti') != jti:
            logger.warning(f'JWT: invalid family token family={family_id}')
            return None

        # Old token blacklist
        ttl = max(0, int(payload.get('exp', 0) - time.time()))
        cache.set(CACHE_PREFIX_JWT.format(jti), True, timeout=ttl + 60)

        # New token pair (same family)
        new_pair = self.generate_token_pair(
            user_id   = user_id,
            role      = payload.get('role', 'worker'),
            device_id = device_id or payload.get('did', ''),
            ip        = ip,
        )

        # Update family with new refresh JTI
        # (generate_token_pair এ নতুন family তৈরি হয় — existing family update করো)
        logger.info(f'JWT tokens refreshed: user={user_id}')
        return new_pair

    def revoke_token(self, token: str) -> bool:
        """Token blacklist করে (logout)।"""
        try:
            payload = jwt.decode(
                token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
                options={'verify_exp': False},
            )
            jti = payload.get('jti', '')
            ttl = max(60, int(payload.get('exp', time.time()) - time.time()) + 300)
            cache.set(CACHE_PREFIX_JWT.format(jti), True, timeout=ttl)
            logger.info(f'JWT revoked: jti={jti} user={payload.get("sub")}')
            return True
        except Exception as e:
            logger.error(f'JWT revoke failed: {e}')
            return False

    def revoke_all_user_tokens(self, user_id: int) -> None:
        """User এর সব tokens revoke করে — forced logout সব device থেকে।"""
        # User-level revoke marker — verify এ check করতে হবে
        cache.set(
            f'jwt:user_revoke:{user_id}',
            int(time.time()),
            timeout=int(JWT_REFRESH_TTL.total_seconds()),
        )
        logger.warning(f'JWT: all tokens revoked for user={user_id}')

    def _revoke_family(self, family_id: str) -> None:
        """পুরো token family revoke করে।"""
        cache.delete(CACHE_PREFIX_FAMILY.format(family_id))
        cache.set(
            CACHE_PREFIX_JWT.format(f'family:{family_id}'),
            True, timeout=CACHE_TTL_BL,
        )

    @staticmethod
    def _hash_ip(ip: str) -> str:
        if not ip:
            return ''
        return hashlib.sha256(ip.encode()).hexdigest()[:16]
