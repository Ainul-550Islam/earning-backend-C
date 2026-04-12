"""
SELLER_MANAGEMENT/seller_business.py — Seller Business Information Management
"""
from api.marketplace.models import SellerProfile
from api.marketplace.SELLER_MANAGEMENT.seller_bank_account import SellerBankAccount


def update_business_info(seller: SellerProfile, **kwargs) -> SellerProfile:
    allowed = [
        "business_type","business_name","trade_license","tin_number",
        "phone","address","city","district","postal_code","country",
    ]
    for key in allowed:
        if key in kwargs:
            setattr(seller, key, kwargs[key])
    seller.save()
    return seller


def get_business_profile(seller: SellerProfile) -> dict:
    return {
        "business_type":    seller.business_type,
        "business_name":    seller.business_name,
        "trade_license":    seller.trade_license,
        "tin_number":       seller.tin_number,
        "phone":            seller.phone,
        "address":          seller.address,
        "city":             seller.city,
        "district":         seller.district,
        "country":          seller.country,
    }


def validate_business_info(data: dict) -> dict:
    errors = []
    if data.get("business_type") == "company":
        if not data.get("business_name","").strip():
            errors.append("Business name required for company type")
        if not data.get("trade_license","").strip():
            errors.append("Trade license required for company type")
    if not data.get("phone","").strip():
        errors.append("Phone number is required")
    return {"valid": len(errors) == 0, "errors": errors}


def get_primary_bank_account(seller: SellerProfile) -> dict:
    account = SellerBankAccount.objects.filter(seller=seller, is_primary=True, is_verified=True).first()
    if not account:
        account = SellerBankAccount.objects.filter(seller=seller).first()
    if not account:
        return {}
    return {
        "account_type":   account.account_type,
        "account_name":   account.account_name,
        "account_number": account.account_number,
        "bank_name":      account.bank_name,
        "is_verified":    account.is_verified,
    }


def business_compliance_status(seller: SellerProfile) -> dict:
    """Check which business documents are present."""
    return {
        "has_trade_license":  bool(seller.trade_license),
        "has_tin":            bool(seller.tin_number),
        "has_bank_account":   SellerBankAccount.objects.filter(seller=seller).exists(),
        "is_kyc_verified":    hasattr(seller, "verification") and seller.verification.status == "verified",
        "compliance_score":   _compliance_score(seller),
    }


def _compliance_score(seller: SellerProfile) -> int:
    score = 0
    if seller.trade_license:   score += 25
    if seller.tin_number:      score += 20
    if SellerBankAccount.objects.filter(seller=seller).exists(): score += 30
    try:
        if seller.verification.status == "verified": score += 25
    except Exception:
        pass
    return score
