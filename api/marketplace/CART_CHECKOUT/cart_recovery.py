"""
CART_CHECKOUT/cart_recovery.py — Cart Recovery Campaigns
"""
import logging
from django.utils import timezone
from api.marketplace.CART_CHECKOUT.abandoned_cart import get_abandoned_carts, build_recovery_email_data

logger = logging.getLogger(__name__)


def run_recovery_campaign(tenant) -> dict:
    """
    Send recovery emails to users who abandoned their carts.
    Called by Celery task every 6 hours.
    """
    abandoned = get_abandoned_carts(tenant, hours=24)
    sent = 0
    for cart in abandoned:
        if not cart.user or not cart.user.email:
            continue
        try:
            email_data = build_recovery_email_data(cart)
            _send_recovery_email(email_data, tenant)
            sent += 1
        except Exception as e:
            logger.error("[CartRecovery] Email failed for cart#%s: %s", cart.pk, e)

    logger.info("[CartRecovery] Sent %s recovery emails for tenant %s", sent, tenant.slug)
    return {"sent": sent, "total_abandoned": len(abandoned)}


def apply_recovery_discount(cart, tenant) -> dict:
    """Apply an auto-generated recovery coupon to an abandoned cart."""
    from api.marketplace.PROMOTION_MARKETING.coupon_manager import create_coupon
    from api.marketplace.enums import CouponType
    from django.utils import timezone
    from datetime import timedelta

    coupon = create_coupon(
        tenant=tenant,
        created_by=None,
        name="Cart Recovery Discount",
        discount_value=10,
        coupon_type=CouponType.PERCENTAGE,
        valid_from=timezone.now(),
        valid_until=timezone.now() + timedelta(hours=48),
        usage_limit=1,
        is_public=False,
    )
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])
    return {"coupon_code": coupon.code, "discount": "10%", "expires_hours": 48}


def _send_recovery_email(data: dict, tenant):
    from api.marketplace.INTEGRATIONS.email_service import send_order_confirmation_email
    from django.core.mail import send_mail
    from django.conf import settings

    subject = f"You left something behind! Complete your order with {tenant.name}"
    items_text = "\n".join(f"  - {i['product']} x{i['qty']} = {i['subtotal']} BDT" for i in data["items"])
    message = (
        f"Hi {data['user_name']},\n\n"
        f"You left these items in your cart:\n{items_text}\n\n"
        f"Cart Total: {data['cart_total']} BDT\n\n"
        f"Complete your order: {data['recovery_link']}\n\n"
        f"Happy shopping!\n{tenant.name}"
    )
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [data["user_email"]], fail_silently=True)
    except Exception as e:
        logger.error("[CartRecovery] send_mail failed: %s", e)
