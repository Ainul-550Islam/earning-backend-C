# api/djoyalty/interactors.py
"""
Djoyalty Interactors -- Complex multi-step business operations।
Interactors are like use cases but can call multiple use cases and services।
Pattern: Interactor (Clean Architecture)।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class CustomerOnboardingInteractor:
    """
    CI-001: Complete customer onboarding flow।
    Creates customer -> creates points account -> assigns default tier ->
    generates referral code -> sends welcome -> logs audit।
    """

    def execute(self, code: str, email: str = '', phone: str = '',
                firstname: str = '', lastname: str = '',
                referred_by_code: str = '', tenant=None) -> dict:
        from .repositories import CustomerRepository, PointsRepository, AuditRepository
        from .helpers import generate_referral_code
        from .models.tiers import LoyaltyTier, UserTier

        # 1. Create customer
        try:
            customer = CustomerRepository.create(
                code=code, email=email, phone=phone,
                firstname=firstname, lastname=lastname, tenant=tenant,
            )
        except Exception as e:
            return {'success': False, 'error': f'Could not create customer: {e}'}

        # 2. Create points account
        PointsRepository.get_or_create(customer)

        # 3. Assign base tier
        base_tier = LoyaltyTier.objects.filter(is_active=True).order_by('rank').first()
        if base_tier:
            UserTier.objects.create(
                customer=customer,
                tier=base_tier,
                is_current=True,
                tenant=tenant,
            )

        # 4. Generate referral code
        ref_code = generate_referral_code()
        customer.referral_code = ref_code
        customer.save(update_fields=['referral_code'])

        from .models.referral import ReferralLink
        ReferralLink.objects.create(customer=customer, code=ref_code, tenant=tenant)

        # 5. Process referral if code given
        if referred_by_code:
            try:
                from .use_cases import ReferralConversionUseCase
                ReferralConversionUseCase().execute(referred_by_code, customer)
            except Exception as e:
                logger.debug('CustomerOnboardingInteractor: referral processing error: %s', e)

        # 6. Send welcome notification
        try:
            from .services.NotificationService import NotificationService
            NotificationService.send(
                customer, 'campaign_active',
                title='🎉 স্বাগতম Loyalty Program এ!',
                body=f'প্রিয় {firstname or code}, আপনার Loyalty account তৈরি হয়েছে!',
                icon='🎉',
                priority='high',
            )
        except Exception as e:
            logger.debug('CustomerOnboardingInteractor: welcome notification error: %s', e)

        # 7. Audit log
        AuditRepository.log(
            action='customer_onboarded',
            category='customer',
            customer=customer,
            new_value={'code': code, 'email': email},
            tenant=tenant,
        )

        return {
            'success': True,
            'customer_id': customer.id,
            'customer_code': customer.code,
            'referral_code': ref_code,
            'tier': base_tier.name if base_tier else 'Bronze',
        }


class ProcessTransactionInteractor:
    """
    CI-002: Process a customer transaction and earn points।
    Validates transaction -> calculates points via earn rules ->
    awards points -> evaluates tier -> checks badges -> notifies।
    """

    def execute(self, customer_id: int, transaction_value: Decimal,
                source: str = 'purchase', reference_id: str = '',
                metadata: dict = None) -> dict:
        from .models.core import Customer, Txn
        from .use_cases import EarnPointsUseCase, EarnPointsInput

        try:
            customer = Customer.objects.get(id=customer_id, is_active=True)
        except Customer.DoesNotExist:
            return {'success': False, 'error': 'Customer not found.'}

        # Create transaction record
        try:
            txn = Txn.objects.create(
                customer=customer,
                tenant=customer.tenant,
                value=transaction_value,
                source=source,
                reference_id=reference_id or '',
            )
        except Exception as e:
            logger.error('ProcessTransactionInteractor: txn creation error: %s', e)
            return {'success': False, 'error': str(e)}

        # Earn points via use case
        result = EarnPointsUseCase().execute(
            EarnPointsInput(
                customer_id=customer_id,
                txn_id=txn.id,
                amount=transaction_value,
                source=source,
                reference_id=reference_id or str(txn.id),
                metadata=metadata,
            )
        )

        return {
            'success': result.success,
            'transaction_id': txn.id,
            'points_earned': str(result.points_earned),
            'new_balance': str(result.new_balance),
            'tier_changed': result.tier_changed,
            'new_tier': result.new_tier,
            'badges_earned': result.badges_earned,
            'error': result.error,
        }
