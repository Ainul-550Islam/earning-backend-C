import random
import string
from django.core.mail import send_mail
from django.conf import settings


def generate_random_string(length=10):
    """Generate random alphanumeric string."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_otp(length=6):
    """Generate random numeric OTP."""
    return ''.join(random.choices(string.digits, k=length))


def send_email(subject, message, recipient_list):
    """Send email utility."""
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email sending failed: {str(e)}")
        return False


def format_phone_number(phone):
    """Format phone number to standard format."""
    # Remove all non-numeric characters
    phone = ''.join(filter(str.isdigit, phone))
    return phone


# core/utils.py ফাইলের নিচে এটি যোগ করুন
def send_async_task(task_func, *args, **kwargs):
    """
    একটি সাধারণ টাস্ক রানার। আপনার যদি সেলারি (Celery) সেটআপ না থাকে, 
    তবে এটি সরাসরি ফাংশনটি কল করবে।
    """
    return task_func(*args, **kwargs)