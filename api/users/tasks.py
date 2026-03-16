from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_otp_email(email, otp_code):
    """Send OTP email to user"""
    subject = 'Your OTP Code'
    message = f'Your OTP code is: {otp_code}. It will expire in 10 minutes.'
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])


@shared_task
def send_welcome_email(email, username):
    """Send welcome email to new user"""
    subject = 'Welcome to Earnify'
    message = f'Hi {username},\n\nWelcome to Earnify! Start earning today.'
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])


@shared_task
def cleanup_expired_otps():
    """Delete expired OTPs"""
    from django.utils import timezone
    from .models import OTP
    
    expired_otps = OTP.objects.filter(expires_at__lt=timezone.now())
    count = expired_otps.count()
    expired_otps.delete()
    return f'Deleted {count} expired OTPs'