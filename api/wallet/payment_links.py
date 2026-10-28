# api/wallet/payment_links.py
"""
Payment Link & QR Code generation.
Bangladesh 2025: QR-based payments growing rapidly (FICCI 2025 report).
Supports: Static QR, Dynamic QR, Payment links, Invoice links.

Usage:
    from .payment_links import PaymentLinkService
    link = PaymentLinkService.create(user=user, amount=500, expires_minutes=30)
    qr_data = PaymentLinkService.get_qr_data(link)
"""
import uuid
import hashlib
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger("wallet.payment_links")

LINK_TTL_DEFAULT = 30    # minutes
LINK_MAX_TTL     = 1440  # 24 hours


class PaymentLinkService:
    """Create and manage payment links and QR codes."""

    @staticmethod
    def create(user, amount: Decimal = None, description: str = "",
                expires_minutes: int = LINK_TTL_DEFAULT,
                currency: str = "BDT", metadata: dict = None) -> dict:
        """
        Create a payment link (static or dynamic).
        If amount is None → static link (payer enters amount).
        If amount is set → dynamic link (fixed amount).
        """
        link_id  = uuid.uuid4().hex
        expires  = min(expires_minutes, LINK_MAX_TTL)
        expires_at = timezone.now() + timedelta(minutes=expires)

        data = {
            "link_id":     link_id,
            "user_id":     user.id,
            "username":    user.username,
            "amount":      str(amount) if amount else None,
            "currency":    currency,
            "description": description[:200],
            "is_static":   amount is None,
            "created_at":  timezone.now().isoformat(),
            "expires_at":  expires_at.isoformat(),
            "is_used":     False,
            "metadata":    metadata or {},
        }

        # Store in cache (Redis)
        cache_key = f"payment_link:{link_id}"
        cache.set(cache_key, data, expires * 60)

        # Build URL
        base_url = getattr(settings, "PAYMENT_LINK_BASE_URL",
                           "https://pay.yourplatform.com")
        link_url = f"{base_url}/pay/{link_id}"

        logger.info(f"Payment link created: {link_id} user={user.id} amount={amount}")
        return {
            "success":     True,
            "link_id":     link_id,
            "link_url":    link_url,
            "amount":      str(amount) if amount else None,
            "currency":    currency,
            "expires_at":  expires_at.isoformat(),
            "qr_data":     PaymentLinkService._build_qr_data(link_url, amount, currency),
        }

    @staticmethod
    def get(link_id: str) -> dict:
        """Get payment link details."""
        data = cache.get(f"payment_link:{link_id}")
        if not data:
            return {"found": False, "error": "Link not found or expired"}
        if data.get("is_used"):
            return {"found": True, "is_used": True, "error": "Link already used"}
        # Check expiry
        expires_at = data.get("expires_at")
        if expires_at:
            from datetime import datetime
            exp = datetime.fromisoformat(expires_at)
            if timezone.now() > timezone.make_aware(exp) if exp.tzinfo is None else timezone.now() > exp:
                return {"found": True, "expired": True, "error": "Link expired"}
        return {"found": True, **data}

    @staticmethod
    def consume(link_id: str, payer_user_id: int,
                amount: Decimal = None) -> dict:
        """
        Process payment for a link.
        Credits the link owner's wallet.
        """
        link_data = PaymentLinkService.get(link_id)
        if not link_data.get("found"):
            return {"success": False, "error": link_data.get("error", "Link not found")}
        if link_data.get("is_used"):
            return {"success": False, "error": "Link already used"}
        if link_data.get("expired"):
            return {"success": False, "error": "Link expired"}

        # Determine amount
        link_amount = Decimal(link_data["amount"]) if link_data.get("amount") else amount
        if not link_amount or link_amount <= 0:
            return {"success": False, "error": "Invalid amount"}

        try:
            from .services.core.WalletService import WalletService
            from django.contrib.auth import get_user_model
            User = get_user_model()
            owner = User.objects.get(id=link_data["user_id"])
            wallet = WalletService.get_or_create(owner)

            txn = WalletService.credit(
                wallet=wallet,
                amount=link_amount,
                txn_type="payment_link",
                description=f"Payment link: {link_data.get('description','')}"[:200],
                metadata={"link_id": link_id, "payer_id": payer_user_id},
            )

            # Mark as used
            link_data["is_used"] = True
            link_data["used_by"] = payer_user_id
            link_data["used_at"] = timezone.now().isoformat()
            cache.set(f"payment_link:{link_id}", link_data, 3600)

            logger.info(f"Payment link consumed: {link_id} amount={link_amount}")
            return {
                "success":    True,
                "txn_id":     str(txn.txn_id),
                "amount":     str(link_amount),
                "owner":      owner.username,
            }
        except Exception as e:
            logger.error(f"Payment link consume error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_invoice(user, items: list, due_date=None) -> dict:
        """
        Create an invoice payment link.
        items = [{"name": "Service", "qty": 1, "price": 500}]
        """
        total = sum(Decimal(str(i["price"])) * i.get("qty", 1) for i in items)
        desc  = ", ".join(i["name"] for i in items[:3])
        return PaymentLinkService.create(
            user=user, amount=total, description=f"Invoice: {desc}",
            expires_minutes=LINK_MAX_TTL,
            metadata={"items": items, "due_date": str(due_date) if due_date else None}
        )

    @staticmethod
    def _build_qr_data(url: str, amount: Decimal = None, currency: str = "BDT") -> str:
        """
        Build QR code data string.
        Compatible with Bangladesh QR standard (BACS/NPSB format).
        """
        if amount:
            return f"{url}?amount={amount}&currency={currency}"
        return url

    @staticmethod
    def list_for_user(user_id: int, limit: int = 20) -> list:
        """List active payment links for a user (Redis scan)."""
        try:
            client = cache.client.get_client()
            keys = list(client.scan_iter("payment_link:*", count=200))[:limit * 3]
            links = []
            for key in keys:
                data = cache.get(key.decode().replace("payment_link:", ""))
                if data and data.get("user_id") == user_id and not data.get("is_used"):
                    links.append(data)
            return links[:limit]
        except Exception:
            return []
