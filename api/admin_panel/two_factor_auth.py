# api/admin_panel/two_factor_auth.py
"""
TOTP Two-Factor Authentication for admin_panel.
Google Authenticator / Authy compatible.
Requires: pip install pyotp qrcode[pil]

Features:
  - TOTP code generation and validation
  - QR code generation for setup
  - Backup codes (8 single-use codes)
  - 2FA enforcement per admin role
  - Recovery flow
  - Rate-limited verification (5 attempts / 15 min)
"""
from __future__ import annotations
import logging
import secrets
from typing import List, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)

# Roles that MUST have 2FA enabled
REQUIRED_2FA_ROLES = getattr(settings, 'ADMIN_2FA_REQUIRED_ROLES',
                              ['superadmin', 'admin', 'finance'])
TOTP_ISSUER       = getattr(settings, 'ADMIN_2FA_ISSUER', 'AdminPanel')
MAX_VERIFY_ATTEMPTS = 5
LOCKOUT_MINUTES     = 15
BACKUP_CODE_COUNT   = 8


class AdminTOTP:
    """TOTP 2FA manager for admin users."""

    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret for a user."""
        try:
            import pyotp
            return pyotp.random_base32()
        except ImportError:
            import base64
            return base64.b32encode(secrets.token_bytes(20)).decode()

    @staticmethod
    def get_totp(secret: str):
        """Get TOTP object for a secret."""
        try:
            import pyotp
            return pyotp.TOTP(secret)
        except ImportError:
            raise ImportError("pyotp not installed. Run: pip install pyotp")

    @classmethod
    def get_qr_uri(cls, user, secret: str) -> str:
        """Get otpauth:// URI for QR code generation."""
        try:
            import pyotp
            totp = pyotp.TOTP(secret)
            return totp.provisioning_uri(
                name=user.email or user.username,
                issuer_name=TOTP_ISSUER,
            )
        except ImportError:
            return f"otpauth://totp/{TOTP_ISSUER}:{user.username}?secret={secret}&issuer={TOTP_ISSUER}"

    @classmethod
    def get_qr_code_base64(cls, user, secret: str) -> str:
        """Generate QR code as base64 PNG for frontend display."""
        uri = cls.get_qr_uri(user, secret)
        try:
            import qrcode
            import io
            import base64
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color='black', back_color='white')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return base64.b64encode(buf.getvalue()).decode()
        except ImportError:
            return ''

    @classmethod
    def verify_code(cls, user, code: str, secret: str) -> Tuple[bool, str]:
        """
        Verify a TOTP code.
        Returns (success, reason).
        Handles rate limiting and window tolerance.
        """
        # Rate limit check
        lock_key = f'admin_panel:2fa_lock:{user.pk}'
        attempt_key = f'admin_panel:2fa_attempts:{user.pk}'

        if cache.get(lock_key):
            return False, f'Too many attempts. Try again in {LOCKOUT_MINUTES} minutes.'

        if not code or not code.strip().isdigit():
            return False, 'Code must be 6 digits.'

        try:
            import pyotp
            totp = pyotp.TOTP(secret)
            # Allow ±1 window (30s tolerance on each side)
            valid = totp.verify(code.strip(), valid_window=1)
        except ImportError:
            return False, 'pyotp not installed on server.'

        if valid:
            cache.delete(attempt_key)
            cache.delete(lock_key)
            return True, 'OK'

        # Track failed attempts
        attempts = cache.get(attempt_key, 0) + 1
        cache.set(attempt_key, attempts, LOCKOUT_MINUTES * 60)
        if attempts >= MAX_VERIFY_ATTEMPTS:
            cache.set(lock_key, True, LOCKOUT_MINUTES * 60)
            logger.warning(f"[2FA] LOCKED: {user.username} after {attempts} failed attempts")
            return False, f'Account locked for {LOCKOUT_MINUTES} minutes.'

        remaining = MAX_VERIFY_ATTEMPTS - attempts
        return False, f'Invalid code. {remaining} attempts remaining.'

    @classmethod
    def generate_backup_codes(cls) -> List[str]:
        """Generate 8 backup codes (each 10 chars, alphanumeric)."""
        codes = []
        for _ in range(BACKUP_CODE_COUNT):
            # Format: XXXXX-XXXXX
            part1 = secrets.token_hex(3).upper()
            part2 = secrets.token_hex(3).upper()
            codes.append(f"{part1}-{part2}")
        return codes

    @classmethod
    def verify_backup_code(cls, user, code: str, stored_codes_hash: List[str]) -> bool:
        """Verify and consume a backup code."""
        import hashlib
        code_hash = hashlib.sha256(code.upper().encode()).hexdigest()
        if code_hash in stored_codes_hash:
            stored_codes_hash.remove(code_hash)
            logger.info(f"[2FA] Backup code used by {user.username}")
            return True
        return False

    @classmethod
    def hash_backup_codes(cls, codes: List[str]) -> List[str]:
        """Hash backup codes for safe storage."""
        import hashlib
        return [hashlib.sha256(c.upper().encode()).hexdigest() for c in codes]


class TwoFactorAuthService:
    """Service layer for 2FA management."""

    @classmethod
    def setup_2fa(cls, user) -> dict:
        """Initialize 2FA setup — generate secret and QR code."""
        secret = AdminTOTP.generate_secret()
        qr_b64 = AdminTOTP.get_qr_code_base64(user, secret)
        uri    = AdminTOTP.get_qr_uri(user, secret)
        backup_codes = AdminTOTP.generate_backup_codes()

        # Store pending setup in cache (not DB until confirmed)
        cache.set(f'admin_panel:2fa_setup:{user.pk}', {
            'secret': secret,
            'backup_hashes': AdminTOTP.hash_backup_codes(backup_codes),
        }, 600)  # 10 min to complete setup

        return {
            'secret': secret,
            'qr_code': qr_b64,
            'qr_uri': uri,
            'backup_codes': backup_codes,  # Show once — never again
            'instructions': [
                '1. Install Google Authenticator or Authy on your phone',
                '2. Scan the QR code',
                '3. Enter the 6-digit code below to confirm setup',
                '4. Save your backup codes in a safe place',
            ],
        }

    @classmethod
    def confirm_2fa_setup(cls, user, code: str) -> Tuple[bool, str]:
        """Confirm 2FA setup with first code verification."""
        pending = cache.get(f'admin_panel:2fa_setup:{user.pk}')
        if not pending:
            return False, '2FA setup session expired. Start again.'

        secret = pending['secret']
        success, reason = AdminTOTP.verify_code(user, code, secret)
        if not success:
            return False, reason

        # Save to AdminProfile
        try:
            profile = user.admin_profile
            profile.totp_secret = secret
            profile.totp_backup_codes = pending['backup_hashes']
            profile.two_fa_enabled = True
            profile.two_fa_enabled_at = timezone.now()
            profile.save(update_fields=['totp_secret', 'totp_backup_codes',
                                        'two_fa_enabled', 'two_fa_enabled_at'])
        except Exception as e:
            logger.error(f"[2FA] Profile save failed: {e}")
            return False, 'Failed to save 2FA settings.'

        cache.delete(f'admin_panel:2fa_setup:{user.pk}')
        logger.info(f"[2FA] Enabled for {user.username}")
        return True, '2FA enabled successfully!'

    @classmethod
    def verify_login_2fa(cls, user, code: str) -> Tuple[bool, str]:
        """Verify 2FA code during login."""
        try:
            profile = user.admin_profile
            if not profile.two_fa_enabled:
                return True, 'no_2fa_required'
            secret = profile.totp_secret
            if not secret:
                return False, '2FA configured but no secret found.'

            # Check if backup code
            if '-' in code:
                backup_codes = profile.totp_backup_codes or []
                if AdminTOTP.verify_backup_code(user, code, backup_codes):
                    profile.totp_backup_codes = backup_codes
                    profile.save(update_fields=['totp_backup_codes'])
                    return True, 'backup_code_used'
                return False, 'Invalid backup code.'

            return AdminTOTP.verify_code(user, code, secret)
        except Exception as e:
            logger.error(f"[2FA] Verify failed for {user.username}: {e}")
            return False, str(e)

    @classmethod
    def disable_2fa(cls, user, code: str, actor) -> Tuple[bool, str]:
        """Disable 2FA (requires current code verification)."""
        success, reason = cls.verify_login_2fa(user, code)
        if not success:
            return False, reason
        try:
            profile = user.admin_profile
            profile.two_fa_enabled = False
            profile.totp_secret = ''
            profile.totp_backup_codes = []
            profile.save(update_fields=['two_fa_enabled', 'totp_secret', 'totp_backup_codes'])
        except Exception as e:
            return False, str(e)
        logger.warning(f"[2FA] Disabled for {user.username} by {actor.username}")
        return True, '2FA disabled.'

    @classmethod
    def is_2fa_required(cls, user) -> bool:
        """Check if 2FA is required for this user's role."""
        try:
            role = user.admin_profile.role
            return role in REQUIRED_2FA_ROLES
        except Exception:
            return user.is_superuser

    @classmethod
    def get_2fa_status(cls, user) -> dict:
        try:
            profile = user.admin_profile
            return {
                'enabled': profile.two_fa_enabled,
                'required': cls.is_2fa_required(user),
                'backup_codes_remaining': len(profile.totp_backup_codes or []),
                'enabled_at': profile.two_fa_enabled_at.isoformat() if profile.two_fa_enabled_at else None,
            }
        except Exception:
            return {'enabled': False, 'required': cls.is_2fa_required(user)}