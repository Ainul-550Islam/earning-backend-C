"""
MARKETPLACE_SAFETY/marketplace_insurance.py — Marketplace Buyer/Seller Insurance
"""
from decimal import Decimal


class BuyerProtectionPolicy:
    """
    Marketplace Buyer Protection:
    - 100% refund if item not received within delivery window
    - Full refund if item significantly not as described
    - Partial refund for minor defects
    """
    COVERAGE_WINDOW_DAYS = 30
    MAX_COVERAGE_BDT     = Decimal("50000")

    @staticmethod
    def is_eligible(order) -> bool:
        from api.marketplace.enums import OrderStatus
        return order.status in (OrderStatus.DELIVERED, OrderStatus.SHIPPED, OrderStatus.OUT_FOR_DELIVERY)

    @staticmethod
    def coverage_amount(order) -> Decimal:
        return min(order.total_price, BuyerProtectionPolicy.MAX_COVERAGE_BDT)

    @staticmethod
    def coverage_summary(order) -> dict:
        return {
            "covered":          BuyerProtectionPolicy.is_eligible(order),
            "max_coverage":     str(BuyerProtectionPolicy.coverage_amount(order)),
            "window_days":      BuyerProtectionPolicy.COVERAGE_WINDOW_DAYS,
            "refund_types":     ["not_received","not_as_described","damaged","defective"],
            "processing_days":  "3-5 business days",
        }


class SellerProtectionPolicy:
    """
    Seller Protection:
    - Escrow holds funds securely
    - Fraud chargeback protection up to 5000 BDT/month
    - Dispute arbitration support
    """
    CHARGEBACK_PROTECTION_BDT = Decimal("5000")

    @staticmethod
    def is_covered(order_item) -> bool:
        from api.marketplace.SELLER_MANAGEMENT.seller_verification import submit_kyc
        return order_item.seller and order_item.seller.status == "active"

    @staticmethod
    def protection_summary(seller) -> dict:
        return {
            "covered":                True,
            "chargeback_limit":       str(SellerProtectionPolicy.CHARGEBACK_PROTECTION_BDT),
            "escrow_protection":      True,
            "dispute_support":        True,
            "instant_payout_eligible":seller.total_sales >= 50,
        }
