# api/referral/use_cases.py
# Use Cases — high-level application workflows (Clean Architecture)
# Each use case represents one user-facing action.
# Use cases call repositories, services, validators — never ORM directly.
# ============================================================

import logging
from decimal import Decimal
from typing import Dict, Optional
from django.db import transaction

logger = logging.getLogger(__name__)


class RegisterReferralUseCase:
    """
    Use case: New user registers via referral code.
    1. Validate referral code
    2. Fraud check
    3. Create Referral + ReferralChain
    4. Award double-sided bonuses
    5. Setup commission expiry
    6. Emit events
    """

    def execute(
        self,
        new_user,
        referral_code: str = '',
        ip: str = '',
        referrer_ip: str = '',
        device_fingerprint: str = '',
    ) -> Dict:
        from api.referral.repositories import ReferralCodeRepository, ReferralRepository, ReferralChainRepository
        from api.referral.services.ReferralFraudService import ReferralFraudService
        from api.referral.services.AdvancedReferralService import DoubleSidedBonusService, CommissionExpiryService
        from api.referral.events import ReferralEvents
        from api.referral.caching import ReferralSettingsCache

        settings = ReferralSettingsCache.get_or_load()
        if not settings or not settings.is_active:
            return {'success': False, 'reason': 'program_inactive'}

        # 1. Resolve referrer
        referrer = None
        code_obj = None
        if referral_code:
            code_obj = ReferralCodeRepository.get_by_code(referral_code)
            if not code_obj:
                return {'success': False, 'reason': 'invalid_code'}
            referrer = code_obj.user

        if not referrer:
            referrer = getattr(new_user, 'referred_by', None)

        if not referrer:
            return {'success': False, 'reason': 'no_referrer'}

        if referrer.id == new_user.id:
            return {'success': False, 'reason': 'self_referral'}

        if ReferralRepository.exists_for_referred_user(new_user):
            return {'success': False, 'reason': 'already_referred'}

        # 2. Fraud check
        fraud_result = ReferralFraudService.check_signup(
            new_user=new_user, referrer=referrer,
            new_user_ip=ip, referrer_ip=referrer_ip,
            device_fingerprint=device_fingerprint,
        )
        is_suspicious = fraud_result.get('action') in ('block', 'hold_commission', 'flag')
        if fraud_result.get('action') == 'block':
            return {'success': False, 'reason': 'fraud_blocked', 'fraud_score': fraud_result.get('fraud_score')}

        # 3. Create Referral + Chain (atomic)
        with transaction.atomic():
            referral = ReferralRepository.create(
                referrer=referrer,
                referred_user=new_user,
                level=1,
                registration_ip=ip,
                referrer_ip=referrer_ip,
                is_suspicious=is_suspicious,
                suspicious_reason=fraud_result.get('reason', '') if is_suspicious else '',
            )
            ReferralChainRepository.build_chain_from_referrals(
                new_referred_user=new_user, referrer=referrer
            )
            if code_obj:
                ReferralCodeRepository.increment_conversions(code_obj.id)

        # 4. Double-sided bonuses
        bonus_result = DoubleSidedBonusService.award_both_bonuses(
            referrer=referrer, referred_user=new_user,
        )

        # 5. Setup commission expiry
        CommissionExpiryService.setup_expiry_for_referral(referral)

        # 6. Emit events
        ReferralEvents.referral_created(
            referrer=referrer, referred_user=new_user, referral_id=referral.id
        )

        return {
            'success':       True,
            'referral_id':   referral.id,
            'bonus_given':   bonus_result,
            'is_suspicious': is_suspicious,
        }


class ProcessCommissionUseCase:
    """
    Use case: User earns money → process referral commissions.
    1. Get referral chain for earner
    2. Calculate commission per level
    3. Apply campaign/surge/tier multipliers
    4. Hold or release commission
    5. Credit wallet
    6. Log everything
    7. Emit events
    """

    def execute(
        self,
        earner,
        earned_amount: Decimal,
        source_type: str,
        source_id: str = '',
    ) -> list:
        from api.referral.repositories import ReferralChainRepository
        from api.referral.services.CommissionService import CommissionService
        from api.referral.logic import calculate_commission, should_hold_commission
        from api.referral.caching import ReferralSettingsCache
        from api.referral.repositories import CommissionRepository
        from api.referral.INTEGRATION_SYSTEM.integ_adapter import WalletAdapter
        from api.referral.events import ReferralEvents
        from django.utils import timezone

        settings = ReferralSettingsCache.get_or_load()
        if not settings or not settings.is_active:
            return []

        # Get ancestors
        chain = ReferralChainRepository.get_ancestors(earner)
        if not chain:
            return []

        # Get multipliers
        campaign = None
        multiplier = Decimal('1')
        try:
            from api.referral.selectors import get_active_campaign
            camp_data = get_active_campaign()
            if camp_data:
                multiplier = Decimal(str(camp_data.get('multiplier', 1)))
        except Exception:
            pass

        results = []
        for chain_entry in chain:
            beneficiary = chain_entry.beneficiary
            level = chain_entry.level

            # Get effective rate (tier-adjusted)
            rate = CommissionService.get_commission_rate(
                level=level, user=beneficiary, settings=settings
            )
            commission = calculate_commission(
                earned_amount=earned_amount,
                commission_rate=rate,
                multiplier=multiplier,
            )
            if commission <= 0:
                continue

            # Check if should hold
            user_age_days = (timezone.now() - beneficiary.date_joined).days
            hold, hold_reason = should_hold_commission(
                is_new_user=user_age_days < settings.commission_hold_days,
                user_age_days=user_age_days,
                fraud_score=0,
                hold_threshold_days=settings.commission_hold_days,
            )
            status = 'held' if hold else 'pending'

            # Create CommissionLog
            with transaction.atomic():
                log = CommissionRepository.create(
                    user=beneficiary,
                    referred_user=earner,
                    level=level,
                    amount=commission,
                    base_amount=earned_amount,
                    commission_rate=rate,
                    action_type=source_type,
                    source_reference=source_id,
                    status=status,
                )

                if hold:
                    from api.referral.models import CommissionHold
                    CommissionHold.objects.create(
                        commission=log,
                        hold_days=settings.commission_hold_days,
                        release_at=timezone.now() + __import__('datetime').timedelta(
                            days=settings.commission_hold_days
                        ),
                        reason=hold_reason,
                    )
                else:
                    # Credit wallet immediately
                    try:
                        wallet_txn = WalletAdapter.credit_referral_commission(
                            user=beneficiary,
                            amount=commission,
                            level=level,
                            referred_user_id=earner.id,
                            source_id=source_id,
                        )
                        CommissionRepository.update_status(
                            log.id, 'released',
                            str(getattr(wallet_txn, 'id', '')) if wallet_txn else '',
                        )
                    except Exception as e:
                        logger.error(f'[UseCase] Wallet credit failed: {e}')

                # Log ReferralEarning for backward compat
                from api.referral.repositories import ReferralEarningRepository
                ReferralEarningRepository.create(
                    referrer=beneficiary,
                    referred_user=earner,
                    level=level,
                    amount=commission,
                    commission_rate=rate,
                    source_amount=earned_amount,
                    source_type=source_type,
                    source_id=source_id,
                    status='released' if not hold else 'held',
                )

            # Emit event
            if not hold:
                ReferralEvents.commission_paid(
                    user=beneficiary, amount=commission,
                    level=level, from_user=earner, source=source_type,
                )

            results.append({
                'beneficiary': beneficiary.username,
                'level':       level,
                'commission':  float(commission),
                'rate':        float(rate),
                'held':        hold,
            })

        return results


class ReviewFraudUseCase:
    """
    Use case: Admin reviews a suspicious referral.
    Actions: clear (legitimate) or confirm (fraud → clawback).
    """

    def execute(
        self,
        suspicious_referral_id: int,
        action: str,  # 'clear' or 'confirm_fraud'
        admin_user,
        notes: str = '',
    ) -> Dict:
        from api.referral.repositories import SuspiciousReferralRepository
        from api.referral.INTEGRATION_SYSTEM.integ_audit_logs import ReferralAuditLogger

        if action not in ('clear', 'confirm_fraud'):
            return {'success': False, 'reason': 'invalid_action'}

        new_status = 'cleared' if action == 'clear' else 'fraud'
        updated = SuspiciousReferralRepository.update_status(
            suspicious_id=suspicious_referral_id,
            status=new_status,
            reviewed_by=admin_user,
            notes=notes,
        )

        if not updated:
            return {'success': False, 'reason': 'not_found'}

        if action == 'confirm_fraud':
            ReferralAuditLogger.log_fraud_confirmed(
                referral_id=suspicious_referral_id,
                admin_user=admin_user,
                notes=notes,
            )
            try:
                from api.referral.tasks.clawback_tasks import initiate_fraud_clawbacks
                initiate_fraud_clawbacks.delay()
            except Exception:
                pass
        else:
            ReferralAuditLogger.log_fraud_cleared(
                referral_id=suspicious_referral_id,
                admin_user=admin_user,
                notes=notes,
            )

        return {'success': True, 'status': new_status}


class CreateCampaignUseCase:
    """Use case: Admin creates a new referral campaign."""

    def execute(self, data: Dict, admin_user) -> Dict:
        from api.referral.models import ReferralCampaign
        from api.referral.helpers import generate_campaign_slug
        from api.referral.INTEGRATION_SYSTEM.integ_audit_logs import ReferralAuditLogger
        from api.referral.caching import ReferralCache, KEY_ACTIVE_CAMPAIGN

        with transaction.atomic():
            campaign = ReferralCampaign.objects.create(
                name=data['name'],
                slug=generate_campaign_slug(data['name']),
                description=data.get('description', ''),
                bonus_multiplier=data.get('bonus_multiplier', 1),
                extra_signup_bonus=data.get('extra_signup_bonus', 0),
                start_date=data['start_date'],
                end_date=data['end_date'],
                max_budget=data.get('max_budget'),
                max_referrals=data.get('max_referrals'),
                terms=data.get('terms', ''),
                is_active=data.get('is_active', True),
                is_featured=data.get('is_featured', False),
                created_by=admin_user,
            )
            ReferralCache.delete(KEY_ACTIVE_CAMPAIGN)

        ReferralAuditLogger.log_campaign_created(
            admin_user=admin_user,
            campaign_id=campaign.id,
            campaign_name=campaign.name,
        )
        return {'success': True, 'campaign_id': campaign.id, 'slug': campaign.slug}


# ── Re-export for convenience ─────────────────────────────────────────────────
from django.db import transaction  # noqa: E402