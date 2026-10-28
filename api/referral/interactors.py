# api/referral/interactors.py
# Interactors — thin orchestrators between views and use cases
# Views call interactors; interactors call use_cases + selectors
# ============================================================

import logging
from decimal import Decimal
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ReferralInteractor:
    """Orchestrates referral registration flow from view layer."""

    def register(self, new_user, referral_code: str = '',
                 ip: str = '', referrer_ip: str = '', device_fp: str = '') -> Dict:
        from api.referral.use_cases import RegisterReferralUseCase
        return RegisterReferralUseCase().execute(
            new_user=new_user, referral_code=referral_code,
            ip=ip, referrer_ip=referrer_ip, device_fingerprint=device_fp,
        )

    def get_stats(self, user) -> Dict:
        from api.referral.selectors import get_user_referral_summary
        return get_user_referral_summary(user)

    def get_commission_history(self, user, **kwargs) -> Dict:
        from api.referral.selectors import get_commission_history
        return get_commission_history(user, **kwargs)


class CommissionInteractor:
    """Orchestrates commission processing."""

    def process(self, earner, earned_amount, source_type: str, source_id: str = '') -> list:
        from api.referral.use_cases import ProcessCommissionUseCase
        return ProcessCommissionUseCase().execute(
            earner=earner,
            earned_amount=Decimal(str(earned_amount)),
            source_type=source_type,
            source_id=source_id,
        )


class AdminReferralInteractor:
    """Orchestrates admin fraud review, campaign management."""

    def review_fraud(self, suspicious_id: int, action: str,
                     admin_user, notes: str = '') -> Dict:
        from api.referral.use_cases import ReviewFraudUseCase
        return ReviewFraudUseCase().execute(
            suspicious_referral_id=suspicious_id,
            action=action, admin_user=admin_user, notes=notes,
        )

    def create_campaign(self, data: Dict, admin_user) -> Dict:
        from api.referral.use_cases import CreateCampaignUseCase
        return CreateCampaignUseCase().execute(data=data, admin_user=admin_user)

    def get_overview(self, days: int = 30, tenant=None) -> Dict:
        from api.referral.selectors import get_admin_overview
        return get_admin_overview(days=days, tenant=tenant)

    def get_fraud_queue(self, **kwargs) -> list:
        from api.referral.selectors import get_fraud_review_queue
        return get_fraud_review_queue(**kwargs)