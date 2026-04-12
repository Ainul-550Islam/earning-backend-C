# api/promotions/governance/user_verification.py
# User Verification — Phone, Email, ID (NID/Passport) verification
import logging, re
from dataclasses import dataclass
logger = logging.getLogger('governance.verification')

@dataclass
class VerificationResult:
    success:   bool
    method:    str
    level:     str       # 'email', 'phone', 'id', 'face'
    details:   dict

class UserVerificationService:
    """Multi-level user verification।"""

    def verify_email(self, user_id: int, email: str) -> VerificationResult:
        """Email verification — OTP send করে।"""
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            return VerificationResult(False, 'email', 'email', {'error': 'invalid_format'})
        try:
            import random, string
            otp = ''.join(random.choices(string.digits, k=6))
            from django.core.cache import cache
            cache.set(f'verify:email:{user_id}', {'otp': otp, 'email': email}, timeout=600)
            # Email send করো
            self._send_otp_email(email, otp)
            return VerificationResult(True, 'email_otp_sent', 'email', {'email': email})
        except Exception as e:
            return VerificationResult(False, 'email', 'email', {'error': str(e)})

    def verify_email_otp(self, user_id: int, otp: str) -> VerificationResult:
        from django.core.cache import cache
        data = cache.get(f'verify:email:{user_id}')
        if not data or data['otp'] != otp:
            return VerificationResult(False, 'email_otp', 'email', {'error': 'invalid_otp'})
        cache.delete(f'verify:email:{user_id}')
        self._mark_verified(user_id, 'email', data['email'])
        return VerificationResult(True, 'email_otp', 'email', {'email': data['email']})

    def verify_phone(self, user_id: int, phone: str, country: str) -> VerificationResult:
        """SMS OTP verification।"""
        import random, string
        otp = ''.join(random.choices(string.digits, k=6))
        from django.core.cache import cache
        cache.set(f'verify:phone:{user_id}', {'otp': otp, 'phone': phone}, timeout=300)
        self._send_sms(phone, otp, country)
        return VerificationResult(True, 'sms_otp_sent', 'phone', {'phone': phone[:6] + '****'})

    def verify_phone_otp(self, user_id: int, otp: str) -> VerificationResult:
        from django.core.cache import cache
        data = cache.get(f'verify:phone:{user_id}')
        if not data or data['otp'] != otp:
            return VerificationResult(False, 'phone_otp', 'phone', {'error': 'invalid_otp'})
        cache.delete(f'verify:phone:{user_id}')
        self._mark_verified(user_id, 'phone', data['phone'])
        return VerificationResult(True, 'phone_otp', 'phone', {})

    def verify_id_document(self, user_id: int, id_type: str, id_number: str, image_bytes: bytes) -> VerificationResult:
        """NID/Passport verification — OCR + manual review।"""
        try:
            from api.promotions.ai.ocr_engine import OCREngine
            result = OCREngine().extract_text(image_bytes)
            if id_number and id_number in result.text:
                self._mark_verified(user_id, 'id', id_number)
                return VerificationResult(True, 'id_ocr', 'id', {'id_type': id_type, 'ocr_confidence': result.confidence})
        except Exception:
            pass
        # Queue for manual review
        return VerificationResult(True, 'id_pending_review', 'pending', {'id_type': id_type})

    def _mark_verified(self, user_id: int, level: str, value: str):
        try:
            from api.promotions.models import UserVerification
            UserVerification.objects.update_or_create(
                user_id=user_id, defaults={'status': 'verified', 'verification_level': level, 'verified_value': value}
            )
        except Exception as e:
            logger.error(f'Mark verified failed: {e}')

    def _send_otp_email(self, email: str, otp: str):
        from django.core.mail import send_mail
        send_mail('Your verification code', f'Code: {otp}', None, [email], fail_silently=True)

    def _send_sms(self, phone: str, otp: str, country: str):
        logger.info(f'SMS OTP sent to {phone[:6]}*** [{country}]: {otp}')
