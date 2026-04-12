"""
PAYMENT_SETTLEMENT/payment_method.py — Payment Method Configuration
====================================================================
"""
from decimal import Decimal
from api.marketplace.enums import PaymentMethod

PAYMENT_METHOD_CONFIG = {
    PaymentMethod.BKASH:  {"label":"bKash",  "icon":"bkash.png",  "enabled":True,  "min":10,    "max":25000,  "daily_limit":25000, "processing_fee_pct":1.5},
    PaymentMethod.NAGAD:  {"label":"Nagad",  "icon":"nagad.png",  "enabled":True,  "min":10,    "max":10000,  "daily_limit":10000, "processing_fee_pct":1.5},
    PaymentMethod.ROCKET: {"label":"Rocket", "icon":"rocket.png", "enabled":True,  "min":10,    "max":10000,  "daily_limit":10000, "processing_fee_pct":1.8},
    PaymentMethod.UPAY:   {"label":"Upay",   "icon":"upay.png",   "enabled":True,  "min":10,    "max":5000,   "daily_limit":5000,  "processing_fee_pct":1.5},
    PaymentMethod.CARD:   {"label":"Card",   "icon":"card.png",   "enabled":False, "min":100,   "max":500000, "daily_limit":500000,"processing_fee_pct":2.5},
    PaymentMethod.BANK:   {"label":"Bank",   "icon":"bank.png",   "enabled":False, "min":1000,  "max":None,   "daily_limit":None,  "processing_fee_pct":0.5},
    PaymentMethod.COD:    {"label":"Cash on Delivery","icon":"cod.png","enabled":True,"min":50, "max":50000,  "daily_limit":None,  "processing_fee_pct":0},
    PaymentMethod.WALLET: {"label":"Wallet", "icon":"wallet.png", "enabled":True,  "min":1,     "max":None,   "daily_limit":None,  "processing_fee_pct":0},
}


def enabled_methods() -> list:
    return [k for k, v in PAYMENT_METHOD_CONFIG.items() if v["enabled"]]


def get_method_config(method: str) -> dict:
    return PAYMENT_METHOD_CONFIG.get(method, {})


def is_method_available(method: str) -> bool:
    cfg = PAYMENT_METHOD_CONFIG.get(method, {})
    return cfg.get("enabled", False)


def validate_amount_for_method(method: str, amount: Decimal) -> dict:
    cfg = get_method_config(method)
    if not cfg:
        return {"valid": False, "error": "Unknown payment method"}
    if not cfg.get("enabled"):
        return {"valid": False, "error": f"{cfg.get('label',method)} is not currently available"}
    min_amt = cfg.get("min", 0)
    max_amt = cfg.get("max")
    if amount < min_amt:
        return {"valid": False, "error": f"Minimum amount for {cfg['label']}: {min_amt} BDT"}
    if max_amt and amount > max_amt:
        return {"valid": False, "error": f"Maximum amount for {cfg['label']}: {max_amt} BDT"}
    return {"valid": True}


def get_processing_fee(method: str, amount: Decimal) -> Decimal:
    cfg = get_method_config(method)
    pct = Decimal(str(cfg.get("processing_fee_pct", 0)))
    return (amount * pct / 100).quantize(Decimal("0.01"))


def get_all_methods_display() -> list:
    return [
        {
            "key":     method,
            "label":   cfg["label"],
            "icon":    cfg["icon"],
            "enabled": cfg["enabled"],
            "min":     cfg["min"],
            "max":     cfg["max"],
        }
        for method, cfg in PAYMENT_METHOD_CONFIG.items()
    ]


def get_cod_available_cities() -> list:
    """Cities where COD is available."""
    from api.marketplace.SHIPPING_LOGISTICS.shipping_city import BD_CITIES
    return list(BD_CITIES.keys())
