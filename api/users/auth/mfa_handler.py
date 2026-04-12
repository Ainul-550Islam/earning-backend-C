"""
api/users/auth/mfa_handler.py
Two-Factor Authentication — TOTP (Google Authenticator) + Backup Codes
pip install pyotp qrcode[pil]
"""
import pyotp
import qrcode
import secrets
import hashlib
import logging
from io import BytesIO
from base64 import b64encode
from django.conf import settings
from django.contrib.auth import get_user_model
from ..exceptions import InvalidOTPException, OTPExpiredException

logger = logging.getLogger(__name__)
User   = get_user_model()

APP_NAME = getattr(settings, 'SITE_NAME', 'EarningApp')


class MFAHandler:

    # ─────────────────────────────────────
    # TOTP SETUP
    # ─────────────────────────────────────
    @staticmethod
    def generate_totp_secret() -> str:
        """নতুন TOTP secret তৈরি করো"""
        return pyotp.random_base32()

    @staticmethod
    def get_totp_uri(secret: str, username: str) -> str:
        """Google Authenticator-এর জন্য URI"""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=username,
            issuer_name=APP_NAME,
        )

    @staticmethod
    def generate_qr_code_base64(totp_uri: str) -> str:
        """QR code generate করো, base64 string return করো"""
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return f"data:image/png;base64,{b64encode(buffer.getvalue()).decode()}"

    # ─────────────────────────────────────
    # TOTP VERIFY
    # ─────────────────────────────────────
    @staticmethod
    def verify_totp(secret: str, code: str) -> bool:
        """TOTP code verify করো (±1 time window)"""
        if not secret or not code:
            return False
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)

    @staticmethod
    def get_current_totp(secret: str) -> str:
        """Current TOTP code দাও (testing-এর জন্য)"""
        return pyotp.TOTP(secret).now()

    # ─────────────────────────────────────
    # BACKUP CODES
    # ─────────────────────────────────────
    @staticmethod
    def generate_backup_codes(count: int = 10) -> list[str]:
        """
        10টি one-time backup code তৈরি করো।
        Format: XXXX-XXXX-XXXX
        """
        codes = []
        for _ in range(count):
            raw = secrets.token_hex(6).upper()
            formatted = f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"
            codes.append(formatted)
        return codes

    @staticmethod
    def hash_backup_code(code: str) -> str:
        """Backup code hash করে store করো (plain text না)"""
        normalized = code.replace('-', '').upper()
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def verify_backup_code(code: str, stored_hashes: list[str]) -> tuple[bool, str | None]:
        """
        Backup code verify করো।
        Returns: (is_valid, matched_hash)
        matched_hash — database থেকে মুছে ফেলো (one-time use)
        """
        normalized = code.replace('-', '').upper()
        code_hash  = hashlib.sha256(normalized.encode()).hexdigest()
        if code_hash in stored_hashes:
            return True, code_hash
        return False, None

    # ─────────────────────────────────────
    # HIGH-LEVEL: Setup flow
    # ─────────────────────────────────────
    @staticmethod
    def initiate_setup(user) -> dict:
        """
        MFA setup শুরু করো।
        Returns: secret, qr_code_base64, backup_codes
        এখনো save করো না — user confirm করলে save করবে।
        """
        secret       = MFAHandler.generate_totp_secret()
        totp_uri     = MFAHandler.get_totp_uri(secret, user.username)
        qr_base64    = MFAHandler.generate_qr_code_base64(totp_uri)
        backup_codes = MFAHandler.generate_backup_codes(10)

        return {
            'secret':         secret,
            'qr_code':        qr_base64,
            'totp_uri':       totp_uri,
            'backup_codes':   backup_codes,
            'backup_hashes':  [MFAHandler.hash_backup_code(c) for c in backup_codes],
        }

    @staticmethod
    def confirm_setup(secret: str, code: str) -> bool:
        """
        User-এর code দিয়ে setup confirm করো।
        Verify হলে secret save করো।
        """
        return MFAHandler.verify_totp(secret, code)

    @staticmethod
    def authenticate(user, code: str, backup_hashes: list[str]) -> tuple[bool, str]:
        """
        Login-এর সময় MFA verify করো।
        Returns: (success, method_used)
        method_used: 'totp' or 'backup_code'
        """
        # TOTP check
        if hasattr(user, 'mfa_secret') and user.mfa_secret:
            if MFAHandler.verify_totp(user.mfa_secret, code):
                return True, 'totp'

        # Backup code check
        is_valid, matched_hash = MFAHandler.verify_backup_code(code, backup_hashes)
        if is_valid:
            return True, 'backup_code'

        return False, ''


# Singleton
mfa_handler = MFAHandler()
