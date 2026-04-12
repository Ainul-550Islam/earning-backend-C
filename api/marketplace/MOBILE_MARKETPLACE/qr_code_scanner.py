"""
MOBILE_MARKETPLACE/qr_code_scanner.py — QR Code Generation & Scanning
"""
import io
import base64
import logging
from api.marketplace.MOBILE_MARKETPLACE.deep_link_manager import product_link, referral_link

logger = logging.getLogger(__name__)


def generate_product_qr(product, size: int = 200) -> str:
    """Returns base64-encoded PNG QR code for a product."""
    return _generate_qr(product_link(product.pk), size)


def generate_referral_qr(code: str, size: int = 200) -> str:
    return _generate_qr(referral_link(code), size)


def generate_seller_store_qr(seller, base_url: str = "", size: int = 200) -> str:
    url = f"{base_url}/store/{seller.store_slug}/" if base_url else referral_link(seller.store_slug)
    return _generate_qr(url, size)


def decode_qr_content(content: str) -> dict:
    """Decode scanned QR content → route info."""
    from api.marketplace.MOBILE_MARKETPLACE.deep_link_manager import resolve_link
    if content.startswith("marketplace://"):
        return resolve_link(content)
    if "/products/" in content:
        slug = content.split("/products/")[-1].strip("/")
        return {"route": "product", "params": {"slug": slug}}
    if "/store/" in content:
        slug = content.split("/store/")[-1].strip("/")
        return {"route": "seller", "params": {"store_slug": slug}}
    return {"route": "web", "params": {"url": content}}


def _generate_qr(data: str, size: int) -> str:
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        logger.warning("[QR] qrcode library not installed: pip install qrcode[pil]")
        return ""
    except Exception as e:
        logger.error("[QR] Generation failed: %s", e)
        return ""
