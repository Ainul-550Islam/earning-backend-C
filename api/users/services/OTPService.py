from django.utils import timezone
from datetime import timedelta
from ..models import OTP, User
from core.utils import generate_otp


class OTPService:
    
    @staticmethod
    def generate_otp(user, otp_type='registration', expiry_minutes=10):
        """Generate and save OTP for user"""
        # Invalidate previous OTPs
        OTP.objects.filter(user=user, otp_type=otp_type, is_used=False).update(is_used=True)
        
        otp_code = generate_otp()
        otp = OTP.objects.create(
            user=user,
            code=otp_code,
            otp_type=otp_type,
            expires_at=timezone.now() + timedelta(minutes=expiry_minutes)
        )
        
        return otp
    
    @staticmethod
    def verify_otp(user_id, otp_code, otp_type='registration'):
        """Verify OTP and return user if valid"""
        try:
            user = User.objects.get(id=user_id)
            otp = OTP.objects.filter(
                user=user,
                code=otp_code,
                otp_type=otp_type,
                is_used=False,
                expires_at__gt=timezone.now()
            ).first()
            
            if not otp:
                return None
            
            otp.is_used = True
            otp.save()
            
            if otp_type == 'registration':
                user.is_verified = True
                user.save()
            
            return user
        except User.DoesNotExist:
            return None