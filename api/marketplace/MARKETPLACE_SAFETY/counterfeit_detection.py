"""
MARKETPLACE_SAFETY/counterfeit_detection.py — Counterfeit Product Detection
"""
import logging
from django.db import models

logger = logging.getLogger(__name__)

PROTECTED_BRANDS = [
    "Apple","Samsung","Nike","Adidas","Rolex","Louis Vuitton","Gucci",
    "Prada","Sony","Microsoft","Google","Amazon","Dell","HP","Lenovo",
]

COUNTERFEIT_KEYWORDS = [
    "replica","fake","copy","first copy","master copy","1:1","china copy",
    "inspired by","high quality replica","7a grade","aaa quality",
]


class ProtectedBrand(models.Model):
    tenant         = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                        related_name="protected_brands_tenant")
    brand_name     = models.CharField(max_length=200, unique=True)
    authorized_sellers = models.ManyToManyField("marketplace.SellerProfile", blank=True)
    is_active      = models.BooleanField(default=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_protected_brand"


def check_product_listing(product) -> dict:
    """Check if a product listing might be counterfeit."""
    flags = []
    text  = f"{product.name} {product.description}".lower()

    # Check counterfeit keywords
    found_keywords = [kw for kw in COUNTERFEIT_KEYWORDS if kw in text]
    if found_keywords:
        flags.append({"type": "counterfeit_keywords", "found": found_keywords, "severity": "high"})

    # Check unauthorized brand mention
    for brand in PROTECTED_BRANDS:
        if brand.lower() in text:
            try:
                pb = ProtectedBrand.objects.get(brand_name__iexact=brand, is_active=True)
                if product.seller not in pb.authorized_sellers.all():
                    flags.append({
                        "type":     "unauthorized_brand",
                        "brand":    brand,
                        "severity": "high",
                        "message":  f"Seller not authorized to sell {brand} products",
                    })
            except ProtectedBrand.DoesNotExist:
                flags.append({
                    "type":     "protected_brand_mention",
                    "brand":    brand,
                    "severity": "medium",
                    "message":  f"Contains protected brand name: {brand}",
                })
            break

    # Suspiciously low price for brand item
    if any(b.lower() in text for b in PROTECTED_BRANDS):
        if product.effective_price < 500:
            flags.append({"type": "suspicious_price", "severity": "high",
                           "message": f"Brand item at very low price: {product.effective_price} BDT"})

    risk = "high" if any(f["severity"] == "high" for f in flags) else ("medium" if flags else "low")
    return {"product_id": product.pk, "risk": risk, "flags": flags, "flag_count": len(flags)}


def scan_new_listings(tenant, limit: int = 100) -> list:
    from api.marketplace.models import Product
    from api.marketplace.enums import ProductStatus
    results = []
    for product in Product.objects.filter(
        tenant=tenant, status=ProductStatus.DRAFT
    ).order_by("-created_at")[:limit]:
        result = check_product_listing(product)
        if result["risk"] != "low":
            results.append(result)
    return results
