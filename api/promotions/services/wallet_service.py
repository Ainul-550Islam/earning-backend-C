# api/promotions/services/wallet_service.py
import logging
from decimal import Decimal
from django.db import transaction
logger = logging.getLogger('services.wallet')

class WalletService:
    def get_balance(self, user_id: int) -> dict:
        try:
            from api.promotions.models import Wallet
            w = Wallet.objects.get(user_id=user_id)
            return {'balance_usd': float(w.balance_usd), 'pending_usd': float(w.pending_usd),
                    'lifetime_earned': float(w.total_earned_usd)}
        except Exception as e:
            return {'error': str(e)}

    def withdraw(self, user_id: int, amount_usd: Decimal, method: str, account: str, country: str) -> dict:
        from api.promotions.auditing.compliance_checker import ComplianceChecker
        compliance = ComplianceChecker().check_transaction(user_id, amount_usd)
        if compliance['requires_review']:
            return {'status': 'pending_review', 'flags': compliance['flags']}
        kyc = ComplianceChecker().check_kyc_status(user_id)
        if not kyc['payout_allowed']:
            return {'error': 'KYC verification required', 'kyc_status': kyc['kyc_status']}
        with transaction.atomic():
            from api.promotions.models import Wallet
            updated = Wallet.objects.filter(user_id=user_id, balance_usd__gte=amount_usd).update(
                balance_usd=models.F('balance_usd') - amount_usd)
            if not updated:
                return {'error': 'Insufficient balance'}
            from api.promotions.localization.local_payment import LocalPaymentGateway, PayoutRequest, PaymentProvider
            result = LocalPaymentGateway().process_payout(PayoutRequest(
                user_id=user_id, amount_usd=amount_usd,
                provider=PaymentProvider(method), account_number=account,
                country=country, currency='USD'))
            if not result.success:
                Wallet.objects.filter(user_id=user_id).update(balance_usd=models.F('balance_usd') + amount_usd)
                return {'error': result.error}
            return {'status': 'processed', 'transaction_id': result.transaction_id, 'amount': float(result.net_usd)}
