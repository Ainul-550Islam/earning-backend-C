# api/users/services/TOTPService.py
# ============================================================
# 2FA TOTP Service — Google Authenticator compatible
# pip install pyotp qrcode[pil]
# ============================================================

import pyotp
import qrcode
import base64
import secrets
import hashlib
from io import BytesIO
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

APP_NAME = getattr(settings, 'APP_NAME', 'EarnSite')


class TOTPService:
    """
    Google Authenticator / Authy compatible 2FA service.
    কাজ: user এর phone এ authenticator app এ scan করার QR code দেওয়া,
    তারপর login এর সময় 6-digit code verify করা।
    """

    @staticmethod
    def generate_secret() -> str:
        """User এর জন্য নতুন TOTP secret key তৈরি করো"""
        return pyotp.random_base32()

    @staticmethod
    def get_totp_uri(user, secret: str) -> str:
        """Authenticator app এর জন্য otpauth:// URI তৈরি করো"""
        totp = pyotp.TOTP(secret)
        label = user.email or user.username
        return totp.provisioning_uri(
            name=label,
            issuer_name=APP_NAME
        )

    @staticmethod
    def generate_qr_code_base64(user, secret: str) -> str:
        """
        QR code image তৈরি করে base64 string হিসেবে return করো।
        Frontend এ <img src="data:image/png;base64,..."> দিয়ে দেখাও।
        """
        uri = TOTPService.get_totp_uri(user, secret)
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode('utf-8')

    @staticmethod
    def verify_totp_code(secret: str, code: str, window: int = 1) -> bool:
        """
        User দেওয়া 6-digit code verify করো।
        window=1 মানে আগের ও পরের 30-second window ও accept করবে।
        """
        if not secret or not code:
            return False
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code.strip(), valid_window=window)
        except Exception as e:
            logger.warning(f"TOTP verify error: {e}")
            return False

    @staticmethod
    def generate_backup_codes(count: int = 10) -> list:
        """
        One-time use backup codes তৈরি করো।
        User যদি phone হারায়, এই codes দিয়ে login করতে পারবে।
        """
        codes = []
        for _ in range(count):
            # Format: XXXXX-XXXXX (easy to type)
            raw = secrets.token_hex(5).upper()
            formatted = f"{raw[:5]}-{raw[5:]}"
            codes.append(formatted)
        return codes

    @staticmethod
    def hash_backup_code(code: str) -> str:
        """Backup code কে hash করে store করো (plain text store করা unsafe)"""
        clean = code.replace('-', '').upper().strip()
        return hashlib.sha256(clean.encode()).hexdigest()

    @staticmethod
    def verify_backup_code(user, code: str) -> bool:
        """
        Backup code verify করো এবং ব্যবহার হলে delete করো।
        SecuritySettings.backup_codes তে hashed list আছে।
        """
        try:
            from api.users.models import SecuritySettings
            settings_obj = SecuritySettings.objects.get(user=user)
            backup_codes = settings_obj.backup_codes or []

            code_hash = TOTPService.hash_backup_code(code)

            if code_hash in backup_codes:
                # একবার ব্যবহারের পর remove করো
                backup_codes.remove(code_hash)
                settings_obj.backup_codes = backup_codes
                settings_obj.save(update_fields=['backup_codes'])
                logger.info(f"Backup code used for user: {user.id}")
                return True

            return False
        except Exception as e:
            logger.error(f"Backup code verify error for user {user.id}: {e}")
            return False

    @staticmethod
    def setup_2fa(user) -> dict:
        """
        2FA setup শুরু করো — secret তৈরি করো, QR code দাও।
        কিন্তু এখনো enable করো না — user verify করলে তারপর enable হবে।
        """
        secret = TOTPService.generate_secret()
        qr_base64 = TOTPService.generate_qr_code_base64(user, secret)

        # Temporarily store secret in cache (10 minutes) — verify করার আগে DB তে save করো না
        cache_key = f"2fa_setup_secret:{user.id}"
        cache.set(cache_key, secret, timeout=600)

        return {
            'secret': secret,
            'qr_code': f"data:image/png;base64,{qr_base64}",
            'manual_entry_key': secret,  # User manually type করতে পারবে
            'instructions': 'Google Authenticator বা Authy app এ QR scan করুন'
        }

    @staticmethod
    def confirm_and_enable_2fa(user, code: str) -> dict:
        """
        User QR scan করে code দিলে verify করো এবং 2FA enable করো।
        """
        cache_key = f"2fa_setup_secret:{user.id}"
        secret = cache.get(cache_key)

        if not secret:
            return {'success': False, 'error': 'Setup expired। আবার শুরু করুন।'}

        if not TOTPService.verify_totp_code(secret, code):
            return {'success': False, 'error': 'Invalid code। Authenticator app থেকে নতুন code দিন।'}

        try:
            from api.users.models import SecuritySettings
            sec, _ = SecuritySettings.objects.get_or_create(user=user)

            # Generate backup codes
            raw_backup_codes = TOTPService.generate_backup_codes(10)
            hashed_codes = [TOTPService.hash_backup_code(c) for c in raw_backup_codes]

            sec.two_factor_enabled = True
            sec.two_factor_method = 'authenticator'
            sec.authenticator_secret = secret
            sec.backup_codes = hashed_codes
            sec.save()

            # Cache থেকে delete করো
            cache.delete(cache_key)

            logger.info(f"2FA enabled for user: {user.id}")
            return {
                'success': True,
                'message': '2FA সফলভাবে চালু হয়েছে!',
                'backup_codes': raw_backup_codes,  # শুধু একবার দেখাও
                'warning': 'Backup codes কোথাও save করুন। এরপর আর দেখাবে না।'
            }
        except Exception as e:
            logger.error(f"2FA enable error for user {user.id}: {e}")
            return {'success': False, 'error': 'Server error। পরে চেষ্টা করুন।'}

    @staticmethod
    def disable_2fa(user, password: str) -> dict:
        """Password confirm করে 2FA disable করো"""
        if not user.check_password(password):
            return {'success': False, 'error': 'Password ভুল।'}

        try:
            from api.users.models import SecuritySettings
            sec = SecuritySettings.objects.get(user=user)
            sec.two_factor_enabled = False
            sec.authenticator_secret = None
            sec.backup_codes = []
            sec.save()
            logger.info(f"2FA disabled for user: {user.id}")
            return {'success': True, 'message': '2FA বন্ধ করা হয়েছে।'}
        except Exception as e:
            logger.error(f"2FA disable error: {e}")
            return {'success': False, 'error': 'Server error।'}

    @staticmethod
    def is_2fa_required(user) -> bool:
        """User এর 2FA চালু আছে কিনা check করো"""
        try:
            from api.users.models import SecuritySettings
            sec = SecuritySettings.objects.filter(user=user).first()
            return sec and sec.two_factor_enabled
        except Exception:
            return False

    @staticmethod
    def verify_2fa_login(user, code: str) -> bool:
        """
        Login এর সময় 2FA code verify করো।
        TOTP code অথবা backup code — দুটোই try করবে।
        """
        try:
            from api.users.models import SecuritySettings
            sec = SecuritySettings.objects.filter(user=user, two_factor_enabled=True).first()
            if not sec:
                return False

            # Rate limiting — 5 বার fail করলে 15 মিনিট block
            rate_key = f"2fa_attempts:{user.id}"
            attempts = cache.get(rate_key, 0)
            if attempts >= 5:
                logger.warning(f"2FA rate limited for user: {user.id}")
                return False

            # TOTP code try করো
            if sec.authenticator_secret:
                if TOTPService.verify_totp_code(sec.authenticator_secret, code):
                    cache.delete(rate_key)
                    return True

            # Backup code try করো
            if TOTPService.verify_backup_code(user, code):
                cache.delete(rate_key)
                return True

            # Failed — counter বাড়াও
            cache.set(rate_key, attempts + 1, timeout=900)  # 15 min
            return False

        except Exception as e:
            logger.error(f"2FA login verify error: {e}")
            return False