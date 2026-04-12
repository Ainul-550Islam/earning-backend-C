"""
INTEGRATIONS/email_service.py — Transactional email service
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_order_confirmation_email(user_email: str, order) -> bool:
    subject = f"আপনার অর্ডার #{order.order_number} কনফার্ম হয়েছে!"
    message = (
        f"প্রিয় {order.shipping_name},\n\n"
        f"আপনার অর্ডার #{order.order_number} সফলভাবে গ্রহণ করা হয়েছে।\n"
        f"মোট পরিমাণ: {order.total_price} টাকা\n\n"
        f"ধন্যবাদ আমাদের সাথে কেনাকাটা করার জন্য!"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False


def send_seller_new_order_email(seller_email: str, order, items) -> bool:
    subject = f"নতুন অর্ডার পেয়েছেন — #{order.order_number}"
    item_lines = "\n".join(f"  - {i.product_name} x{i.quantity}" for i in items)
    message = (
        f"আপনার স্টোরে নতুন অর্ডার এসেছে:\n\n"
        f"অর্ডার নম্বর: #{order.order_number}\n"
        f"পণ্যসমূহ:\n{item_lines}\n\n"
        f"দ্রুত প্যাক করুন এবং পাঠান।"
    )
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [seller_email], fail_silently=False)
        return True
    except Exception as e:
        logger.error("Seller email failed: %s", e)
        return False
