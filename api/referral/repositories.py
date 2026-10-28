# api/referral/repositories.py
# Repository Pattern — all DB queries centralized here
# Services call repositories; repositories call Django ORM
# Makes testing easier (mock the repo, not the ORM)
# ============================================================

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.db.models import Sum, Count, Q, F, Avg
from django.utils import timezone
from datetime import timedelta
from api.referral.models.commission import CommissionLog

logger = logging.getLogger(__name__)


class ReferralRepository:
    """All DB operations for the Referral model."""

    @staticmethod
    def get_by_id(referral_id: int):
        from api.referral.models import Referral
        return Referral.objects.filter(id=referral_id).first()

    @staticmethod
    def get_by_referred_user(user):
        from api.referral.models import Referral
        return Referral.objects.filter(referred_user=user).first()

    @staticmethod
    def get_referrer_of(user):
        """Get the user who referred `user`, or None."""
        ref = ReferralRepository.get_by_referred_user(user)
        return ref.referrer if ref else None

    @staticmethod
    def exists_for_referred_user(user) -> bool:
        from api.referral.models import Referral
        return Referral.objects.filter(referred_user=user).exists()

    @staticmethod
    def count_for_referrer(user) -> int:
        from api.referral.models import Referral
        return Referral.objects.filter(referrer=user).count()

    @staticmethod
    def count_active_for_referrer(user) -> int:
        from api.referral.models import Referral
        return Referral.objects.filter(referrer=user, is_suspicious=False).count()

    @staticmethod
    def get_all_for_referrer(user, limit: int = None):
        from api.referral.models import Referral
        qs = Referral.objects.filter(
            referrer=user
        ).select_related('referred_user').order_by('-created_at')
        if limit:
            qs = qs[:limit]
        return qs

    @staticmethod
    def create(referrer, referred_user, level: int = 1,
               registration_ip: str = '', referrer_ip: str = '',
               is_suspicious: bool = False, suspicious_reason: str = ''):
        from api.referral.models import Referral
        return Referral.objects.create(
            referrer=referrer,
            referred_user=referred_user,
            level=level,
            registration_ip=registration_ip or None,
            referrer_ip=referrer_ip or None,
            is_suspicious=is_suspicious,
            suspicious_reason=suspicious_reason,
        )

    @staticmethod
    def mark_suspicious(referral_id: int, reason: str) -> bool:
        from api.referral.models import Referral
        updated = Referral.objects.filter(id=referral_id).update(
            is_suspicious=True,
            suspicious_reason=reason,
        )
        return updated > 0

    @staticmethod
    def get_same_ip_referrals(ip: str, days: int = 7):
        from api.referral.models import Referral
        cutoff = timezone.now() - timedelta(days=days)
        return Referral.objects.filter(
            Q(registration_ip=ip) | Q(referrer_ip=ip),
            created_at__gte=cutoff,
        )


class ReferralCodeRepository:
    """All DB operations for ReferralCode model."""

    @staticmethod
    def get_by_code(code: str):
        from api.referral.models import ReferralCode
        return ReferralCode.objects.filter(
            Q(code__iexact=code) | Q(custom_code__iexact=code),
            is_active=True,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).select_related('user').first()

    @staticmethod
    def get_primary_for_user(user):
        from api.referral.models import ReferralCode
        return ReferralCode.objects.filter(
            user=user, is_primary=True, is_active=True
        ).first()

    @staticmethod
    def get_or_create_primary(user):
        from api.referral.models import ReferralCode
        from api.referral.helpers import generate_referral_code
        code_obj, created = ReferralCode.objects.get_or_create(
            user=user,
            is_primary=True,
            defaults={
                'code': generate_referral_code(),
                'is_active': True,
            }
        )
        # Ensure user model also has the code
        if user.referral_code != code_obj.code:
            type(user).objects.filter(id=user.id).update(
                referral_code=code_obj.code
            )
        return code_obj, created

    @staticmethod
    def increment_clicks(code_id: int, unique: bool = False) -> None:
        from api.referral.models import ReferralCode
        update = {'clicks': F('clicks') + 1}
        if unique:
            update['unique_clicks'] = F('unique_clicks') + 1
        ReferralCode.objects.filter(id=code_id).update(**update)

    @staticmethod
    def increment_conversions(code_id: int) -> None:
        from api.referral.models import ReferralCode
        ReferralCode.objects.filter(id=code_id).update(
            conversions=F('conversions') + 1
        )

    @staticmethod
    def get_top_codes(limit: int = 10):
        from api.referral.models import ReferralCode
        return ReferralCode.objects.filter(
            is_active=True
        ).order_by('-conversions')[:limit]


class CommissionRepository:
    """All DB operations for CommissionLog model."""

    @staticmethod
    def create(user, referred_user, level: int, amount: Decimal,
               base_amount: Decimal, commission_rate: Decimal,
               action_type: str = 'task', source_reference: str = '',
               campaign=None, rule=None, status: str = 'pending') -> 'CommissionLog':
        from api.referral.models import CommissionLog
        return CommissionLog.objects.create(
            user=user,
            referred_user=referred_user,
            level=level,
            amount=amount,
            base_amount=base_amount,
            commission_rate=commission_rate,
            action_type=action_type,
            source_reference=source_reference,
            campaign=campaign,
            rule=rule,
            status=status,
        )

    @staticmethod
    def get_by_id(log_id: int):
        from api.referral.models import CommissionLog
        return CommissionLog.objects.filter(id=log_id).first()

    @staticmethod
    def get_held_overdue():
        from api.referral.models import CommissionLog
        return CommissionLog.objects.filter(
            status='held',
            hold__release_at__lt=timezone.now(),
            hold__is_released=False,
        ).select_related('user', 'referred_user')

    @staticmethod
    def update_status(log_id: int, status: str, wallet_txn_id: str = '') -> bool:
        from api.referral.models import CommissionLog
        kwargs = {'status': status, 'updated_at': timezone.now()}
        if wallet_txn_id:
            kwargs['wallet_transaction_id'] = wallet_txn_id
        updated = CommissionLog.objects.filter(id=log_id).update(**kwargs)
        return updated > 0

    @staticmethod
    def total_for_user(user, status: str = 'released') -> Decimal:
        from api.referral.models import CommissionLog
        result = CommissionLog.objects.filter(
            user=user, status=status
        ).aggregate(t=Sum('amount'))['t']
        return result or Decimal('0')

    @staticmethod
    def total_this_month(user) -> Decimal:
        from api.referral.models import CommissionLog
        n = timezone.now()
        result = CommissionLog.objects.filter(
            user=user,
            status='released',
            created_at__year=n.year,
            created_at__month=n.month,
        ).aggregate(t=Sum('amount'))['t']
        return result or Decimal('0')

    @staticmethod
    def breakdown_by_level(user) -> Dict:
        from api.referral.models import CommissionLog
        rows = CommissionLog.objects.filter(
            user=user, status='released'
        ).values('level').annotate(
            total=Sum('amount'),
            count=Count('id'),
        )
        return {row['level']: {'total': float(row['total'] or 0), 'count': row['count']} for row in rows}


class ReferralEarningRepository:
    """All DB operations for ReferralEarning model."""

    @staticmethod
    def create(referrer, referred_user, level: int, amount: Decimal,
               commission_rate: Decimal, source_amount: Decimal,
               source_type: str = 'task', source_id: str = '',
               referral=None, campaign_multiplier: Decimal = Decimal('1'),
               status: str = 'released'):
        from api.referral.models import ReferralEarning
        return ReferralEarning.objects.create(
            referrer=referrer,
            referred_user=referred_user,
            referral=referral,
            level=level,
            amount=amount,
            commission_rate=commission_rate,
            source_amount=source_amount,
            source_type=source_type,
            source_id=source_id,
            campaign_multiplier=campaign_multiplier,
            status=status,
        )

    @staticmethod
    def total_for_referrer(user) -> Decimal:
        from api.referral.models import ReferralEarning
        result = ReferralEarning.objects.filter(
            referrer=user, status='released'
        ).aggregate(t=Sum('amount'))['t']
        return result or Decimal('0')


class SuspiciousReferralRepository:
    """All DB operations for SuspiciousReferral model."""

    @staticmethod
    def get_or_create_for_referral(referral, fraud_score: int, flags: dict, evidence: dict):
        from api.referral.models import SuspiciousReferral
        sr, created = SuspiciousReferral.objects.get_or_create(
            referral=referral,
            defaults={
                'fraud_score': fraud_score,
                'flags': flags,
                'evidence': evidence,
                'status': 'pending',
            }
        )
        if not created and sr.fraud_score < fraud_score:
            sr.fraud_score = fraud_score
            sr.flags.update(flags)
            sr.evidence.update(evidence)
            sr.save(update_fields=['fraud_score', 'flags', 'evidence'])
        return sr, created

    @staticmethod
    def get_pending_high_risk(min_score: int = 50):
        from api.referral.models import SuspiciousReferral
        return SuspiciousReferral.objects.filter(
            status='pending',
            fraud_score__gte=min_score,
        ).select_related('referral__referrer', 'referral__referred_user')

    @staticmethod
    def update_status(suspicious_id: int, status: str,
                      reviewed_by=None, notes: str = '') -> bool:
        from api.referral.models import SuspiciousReferral
        update = {
            'status': status,
            'review_notes': notes,
            'reviewed_at': timezone.now(),
        }
        if reviewed_by:
            update['reviewed_by'] = reviewed_by
        updated = SuspiciousReferral.objects.filter(id=suspicious_id).update(**update)
        return updated > 0


class ReferralCampaignRepository:
    """All DB operations for ReferralCampaign model."""

    @staticmethod
    def get_active_campaign():
        from api.referral.models import ReferralCampaign
        now = timezone.now()
        return ReferralCampaign.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
        ).filter(
            Q(max_budget__isnull=True) | Q(current_spend__lt=F('max_budget'))
        ).filter(
            Q(max_referrals__isnull=True) | Q(current_referrals__lt=F('max_referrals'))
        ).order_by('-bonus_multiplier', '-is_featured').first()

    @staticmethod
    def increment_referral_count(campaign_id: int) -> None:
        from api.referral.models import ReferralCampaign
        ReferralCampaign.objects.filter(id=campaign_id).update(
            current_referrals=F('current_referrals') + 1
        )

    @staticmethod
    def increment_spend(campaign_id: int, amount: Decimal) -> None:
        from api.referral.models import ReferralCampaign
        ReferralCampaign.objects.filter(id=campaign_id).update(
            current_spend=F('current_spend') + amount
        )


class ReferralTreeRepository:
    """All DB operations for ReferralTree model."""

    @staticmethod
    def get_for_user(user):
        from api.referral.models import ReferralTree
        return ReferralTree.objects.filter(root_user=user).first()

    @staticmethod
    def get_or_create_for_user(user):
        from api.referral.models import ReferralTree
        return ReferralTree.objects.get_or_create(root_user=user)

    @staticmethod
    def update_stats(tree_id: int, stats: dict) -> None:
        from api.referral.models import ReferralTree
        ReferralTree.objects.filter(id=tree_id).update(
            **stats,
            last_rebuilt_at=timezone.now(),
        )

    @staticmethod
    def get_stale_trees(days: int = 7):
        from api.referral.models import ReferralTree
        cutoff = timezone.now() - timedelta(days=days)
        return ReferralTree.objects.filter(
            Q(last_rebuilt_at__lt=cutoff) | Q(last_rebuilt_at__isnull=True)
        ).select_related('root_user')


class ReferralChainRepository:
    """All DB operations for ReferralChain model."""

    @staticmethod
    def get_ancestors(earner) -> List:
        """Get all beneficiaries (ancestors) of earner in order."""
        from api.referral.models import ReferralChain
        return list(
            ReferralChain.objects.filter(
                earner=earner
            ).select_related('beneficiary').order_by('level')
        )

    @staticmethod
    def create_chain(beneficiary, earner, level: int):
        from api.referral.models import ReferralChain
        return ReferralChain.objects.get_or_create(
            beneficiary=beneficiary,
            earner=earner,
            level=level,
        )

    @staticmethod
    def build_chain_from_referrals(new_referred_user, referrer) -> List:
        """
        Build L1/L2/L3 chain for a new referred user.
        referrer → L1 beneficiary
        referrer's referrer → L2 beneficiary
        referrer's referrer's referrer → L3 beneficiary
        """
        from api.referral.models import Referral, ReferralChain
        created_chains = []

        # L1: direct referrer
        chain, _ = ReferralChainRepository.create_chain(
            beneficiary=referrer, earner=new_referred_user, level=1
        )
        created_chains.append(chain)

        # L2: referrer's referrer
        l2_ref = Referral.objects.filter(referred_user=referrer).first()
        if l2_ref:
            chain2, _ = ReferralChainRepository.create_chain(
                beneficiary=l2_ref.referrer, earner=new_referred_user, level=2
            )
            created_chains.append(chain2)

            # L3: L2's referrer
            l3_ref = Referral.objects.filter(referred_user=l2_ref.referrer).first()
            if l3_ref:
                chain3, _ = ReferralChainRepository.create_chain(
                    beneficiary=l3_ref.referrer, earner=new_referred_user, level=3
                )
                created_chains.append(chain3)

        return created_chains