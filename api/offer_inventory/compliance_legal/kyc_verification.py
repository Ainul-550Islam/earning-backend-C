# api/offer_inventory/compliance_legal/kyc_verification.py
"""KYC Verification Service — Full KYC workflow management."""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class KYCVerificationService:
    """KYC document submission and review workflow."""

    @staticmethod
    def submit(user, id_type: str, id_number: str,
               front_url: str, back_url: str, selfie_url: str) -> object:
        from api.offer_inventory.models import UserKYC
        from api.offer_inventory.validators import validate_nid
        if id_type == 'nid':
            validate_nid(id_number)
        kyc, _ = UserKYC.objects.update_or_create(
            user=user,
            defaults={
                'id_type'     : id_type,
                'id_number'   : id_number,
                'id_front_url': front_url,
                'id_back_url' : back_url,
                'selfie_url'  : selfie_url,
                'status'      : 'pending',
            }
        )
        logger.info(f'KYC submitted: user={user.id} type={id_type}')
        return kyc

    @staticmethod
    def auto_check(kyc) -> dict:
        """Basic automated pre-checks before human review."""
        checks = {
            'has_id_number' : bool(kyc.id_number),
            'has_front_doc' : bool(kyc.id_front_url),
            'has_selfie'    : bool(kyc.selfie_url),
        }
        import re
        if kyc.id_type == 'nid' and kyc.id_number:
            checks['nid_format'] = bool(re.fullmatch(r'\d{10}|\d{17}', kyc.id_number))
        passed = all(checks.values())
        return {'passed': passed, 'checks': checks}

    @staticmethod
    def approve(kyc, reviewer) -> bool:
        from api.offer_inventory.models import UserKYC
        UserKYC.objects.filter(id=kyc.id).update(
            status     ='approved',
            reviewed_by=reviewer,
            reviewed_at=timezone.now(),
        )
        logger.info(f'KYC approved: user={kyc.user_id} by={reviewer.id}')
        return True

    @staticmethod
    def reject(kyc, reviewer, reason: str) -> bool:
        from api.offer_inventory.models import UserKYC
        UserKYC.objects.filter(id=kyc.id).update(
            status       ='rejected',
            reviewed_by  =reviewer,
            reviewed_at  =timezone.now(),
            reject_reason=reason,
        )
        logger.info(f'KYC rejected: user={kyc.user_id} reason={reason}')
        return True

    @staticmethod
    def get_pending_queue(limit: int = 50) -> list:
        from api.offer_inventory.models import UserKYC
        return list(
            UserKYC.objects.filter(status='pending')
            .select_related('user')
            .order_by('created_at')
            .values('id', 'user__username', 'id_type', 'created_at')
            [:limit]
        )

    @staticmethod
    def get_stats() -> dict:
        from api.offer_inventory.models import UserKYC
        from django.db.models import Count
        return dict(
            UserKYC.objects.values_list('status').annotate(count=Count('id'))
        )
