"""PAYMENT_PROCESSING/invoice_generator.py — Invoice generation."""
from decimal import Decimal
from datetime import date


class InvoiceGenerator:
    """Generates payment invoice data structures."""

    @classmethod
    def generate(cls, user, amount: Decimal, currency: str,
                  items: list, invoice_number: str = None) -> dict:
        from django.utils import timezone
        now = timezone.now()
        return {
            "invoice_number": invoice_number or f"INV-{now.strftime('%Y%m%d%H%M%S')}",
            "issued_at":      str(now.date()),
            "due_at":         str(date.fromordinal(now.toordinal() + 15)),
            "customer": {
                "id":       user.id,
                "name":     getattr(user, "get_full_name", lambda: user.username)(),
                "email":    user.email,
                "username": user.username,
            },
            "line_items": items,
            "subtotal":   str(amount),
            "tax":        str((amount * Decimal("0.00")).quantize(Decimal("0.01"))),
            "total":      str(amount),
            "currency":   currency,
            "status":     "unpaid",
        }

    @classmethod
    def for_subscription(cls, user, subscription, payment=None) -> dict:
        items = [{"description": f"Subscription: {subscription.plan.name}",
                  "amount": str(subscription.plan.price), "qty": 1}]
        return cls.generate(user, subscription.plan.price,
                             subscription.plan.currency, items)
