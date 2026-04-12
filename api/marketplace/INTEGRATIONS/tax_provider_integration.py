"""
INTEGRATIONS/tax_provider_integration.py — Bangladesh Tax (VAT/NBR) Integration
"""
from decimal import Decimal

BD_VAT_RATES = {
    "default":         Decimal("0.15"),   # 15% standard VAT
    "electronics":     Decimal("0.15"),
    "fashion":         Decimal("0.15"),
    "food":            Decimal("0.00"),   # most food exempt
    "medicine":        Decimal("0.00"),   # medicines exempt
    "books":           Decimal("0.00"),   # books exempt
    "software":        Decimal("0.15"),
    "services":        Decimal("0.15"),
}

SD_RATES = {                              # Supplementary Duty on some categories
    "tobacco":         Decimal("0.65"),
    "mobile_phones":   Decimal("0.25"),
    "cars":            Decimal("0.45"),
}


def calculate_bd_vat(amount: Decimal, category_slug: str = "default") -> Decimal:
    rate = BD_VAT_RATES.get(category_slug, BD_VAT_RATES["default"])
    return (amount * rate).quantize(Decimal("0.01"))


def calculate_sd(amount: Decimal, category_slug: str) -> Decimal:
    rate = SD_RATES.get(category_slug, Decimal("0"))
    return (amount * rate).quantize(Decimal("0.01"))


def tax_breakdown(amount: Decimal, category_slug: str = "default") -> dict:
    vat_rate = BD_VAT_RATES.get(category_slug, BD_VAT_RATES["default"])
    sd_rate  = SD_RATES.get(category_slug, Decimal("0"))
    vat      = (amount * vat_rate).quantize(Decimal("0.01"))
    sd       = (amount * sd_rate).quantize(Decimal("0.01"))
    total    = vat + sd
    return {
        "amount":       str(amount),
        "vat_rate":     str(vat_rate * 100) + "%",
        "vat_amount":   str(vat),
        "sd_rate":      str(sd_rate * 100) + "%",
        "sd_amount":    str(sd),
        "total_tax":    str(total),
        "total_payable":str(amount + total),
    }


def get_effective_tax_rate(category_slug: str) -> Decimal:
    vat = BD_VAT_RATES.get(category_slug, BD_VAT_RATES["default"])
    sd  = SD_RATES.get(category_slug, Decimal("0"))
    return vat + sd


def generate_vat_invoice_number(seller_bin: str) -> str:
    """Generate NBR-compliant VAT invoice number."""
    import random
    from django.utils import timezone
    date_str = timezone.now().strftime("%Y%m%d")
    seq      = str(random.randint(10000, 99999))
    return f"VATINV-{seller_bin}-{date_str}-{seq}"
