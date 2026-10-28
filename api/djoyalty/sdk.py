# api/djoyalty/sdk.py
"""
Djoyalty Python SDK -- Easy integration layer for external systems।
One-line API for earn/redeem/cashout/customer management।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class DjoyaltySDK:
    """
    High-level Python SDK for Djoyalty।
    Abstracts all complexity into simple method calls।
    Perfect for integrating loyalty into existing Django apps।

    Usage:
        loyalty = DjoyaltySDK(tenant=my_tenant)

        # Earn points
        result = loyalty.earn(customer_id=1, amount=1500, source='purchase', ref='ORDER-001')

        # Redeem
        result = loyalty.redeem(customer_id=1, points=100)

        # Get profile
        profile = loyalty.get_profile(customer_id=1)

        # Cashout
        result = loyalty.cashout(customer_id=1, points=500, method='bkash', wallet_id=3)
    """

    def __init__(self, tenant=None):
        self.tenant = tenant

    # ─── Customer ────────────────────────────────────────────────

    def create_customer(self, code: str, email: str = '', phone: str = '',
                         firstname: str = '', lastname: str = '') -> dict:
        """Create and onboard a new loyalty customer।"""
        from .interactors import CustomerOnboardingInteractor
        return CustomerOnboardingInteractor().execute(
            code=code, email=email, phone=phone,
            firstname=firstname, lastname=lastname,
            tenant=self.tenant,
        )

    def get_customer(self, customer_id: int = None, code: str = None,
                      phone: str = None) -> Optional[object]:
        """Get customer by ID, code, or phone।"""
        from .repositories import CustomerRepository
        if customer_id:
            return CustomerRepository.get_by_id(customer_id)
        if code:
            return CustomerRepository.get_by_code(code, self.tenant)
        if phone:
            return CustomerRepository.get_by_phone(phone, self.tenant)
        return None

    def get_profile(self, customer_id: int) -> dict:
        """Get complete loyalty profile for a customer।"""
        from .selectors import get_customer_loyalty_summary
        customer = self.get_customer(customer_id=customer_id)
        if not customer:
            return {'error': 'Customer not found'}
        return get_customer_loyalty_summary(customer)

    # ─── Points ─────────────────────────────────────────────────

    def earn(self, customer_id: int, amount: Decimal, source: str = 'purchase',
              ref: str = '', metadata: dict = None) -> dict:
        """Award points for a transaction।"""
        from .use_cases import EarnPointsUseCase, EarnPointsInput
        result = EarnPointsUseCase().execute(EarnPointsInput(
            customer_id=customer_id,
            amount=Decimal(str(amount)),
            source=source,
            reference_id=ref,
            metadata=metadata,
        ))
        return {
            'success': result.success,
            'points_earned': str(result.points_earned),
            'new_balance': str(result.new_balance),
            'tier_changed': result.tier_changed,
            'new_tier': result.new_tier,
            'error': result.error,
        }

    def redeem(self, customer_id: int, points: Decimal,
                redemption_type: str = 'voucher') -> dict:
        """Redeem points for a reward।"""
        from .use_cases import RedeemPointsUseCase, RedeemPointsInput
        result = RedeemPointsUseCase().execute(RedeemPointsInput(
            customer_id=customer_id,
            points=Decimal(str(points)),
            redemption_type=redemption_type,
        ))
        return {
            'success': result.success,
            'redemption_id': result.redemption_id,
            'new_balance': str(result.new_balance),
            'error': result.error,
        }

    def get_balance(self, customer_id: int) -> Decimal:
        """Get current points balance।"""
        from .repositories import PointsRepository
        customer = self.get_customer(customer_id=customer_id)
        if not customer:
            return Decimal('0')
        return PointsRepository.get_balance(customer)

    def get_history(self, customer_id: int, limit: int = 20) -> list:
        """Get points ledger history।"""
        from .repositories import PointsRepository
        customer = self.get_customer(customer_id=customer_id)
        if not customer:
            return []
        entries = PointsRepository.get_ledger(customer, limit=limit)
        return [
            {
                'type': e.txn_type,
                'points': str(e.points),
                'source': e.source,
                'balance_after': str(e.balance_after),
                'date': e.created_at.isoformat(),
                'description': e.description or '',
            }
            for e in entries
        ]

    # ─── Cashout ─────────────────────────────────────────────────

    def cashout(self, customer_id: int, points: Decimal,
                 method: str = 'mobile_wallet', wallet_id: int = None) -> dict:
        """Initiate a points cashout request।"""
        from .use_cases import CashoutRequestUseCase, CashoutInput
        result = CashoutRequestUseCase().execute(CashoutInput(
            customer_id=customer_id,
            points=Decimal(str(points)),
            method=method,
            wallet_id=wallet_id,
        ))
        return {
            'success': result.success,
            'cashout_id': result.cashout_id,
            'reference': result.reference,
            'cash_amount': str(result.cash_amount),
            'error': result.error,
        }

    # ─── POS ────────────────────────────────────────────────────

    def pos_checkout(self, identifier: str, order_amount: Decimal,
                      order_ref: str, identifier_type: str = 'phone',
                      redeem_points: Decimal = Decimal('0')) -> dict:
        """Process a POS checkout।"""
        from .pos_integration import POSLoyaltyService, POSCheckoutPayload
        payload = POSCheckoutPayload(
            customer_identifier=identifier,
            identifier_type=identifier_type,
            order_amount=Decimal(str(order_amount)),
            order_reference=order_ref,
            redeem_points=Decimal(str(redeem_points)),
        )
        result = POSLoyaltyService.process_checkout(payload, tenant=self.tenant)
        return result.to_dict()

    # ─── Notifications ───────────────────────────────────────────

    def send_notification(self, customer_id: int, notification_type: str,
                            title: str, body: str) -> bool:
        """Send a notification to a customer।"""
        from .services.NotificationService import NotificationService
        customer = self.get_customer(customer_id=customer_id)
        if not customer:
            return False
        return NotificationService.send(customer, notification_type, title, body)

    # ─── Analytics ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get loyalty program statistics for the tenant।"""
        from .selectors import get_dashboard_stats
        return get_dashboard_stats(tenant=self.tenant)

    def search_customers(self, query: str, limit: int = 10) -> list:
        """Search customers by name/phone/email/code।"""
        from .search import CustomerSearch
        customers = CustomerSearch.search(query, tenant=self.tenant, limit=limit)
        return [
            {'id': c.id, 'code': c.code, 'name': f'{c.firstname or ""} {c.lastname or ""}'.strip(),
             'phone': c.phone or '', 'email': c.email or ''}
            for c in customers
        ]


# Module-level convenience factory
def get_sdk(tenant=None) -> DjoyaltySDK:
    """Get a DjoyaltySDK instance for a tenant।"""
    return DjoyaltySDK(tenant=tenant)
