import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class KYCService:

    @staticmethod
    def get_kyc_status(user) -> Optional[Dict[str, Any]]:
        try:
            from .models import KYC
            kyc = KYC.objects.filter(user=user).first()
            if not kyc:
                return {"status": "not_submitted", "verified": False}
            return {
                "status": kyc.status,
                "verified": kyc.status == 'verified',
                "document_type": getattr(kyc, 'document_type', None),
                "rejection_reason": kyc.rejection_reason if kyc.status == 'rejected' else None,
                "submitted_at": kyc.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
        except Exception as e:
            logger.error("KYC status error: %s", e)
            return None

    @staticmethod
    def check_duplicate(kyc) -> bool:
        from .models import KYC
        if kyc.document_number:
            if KYC.objects.filter(
                document_number=kyc.document_number,
                status='verified'
            ).exclude(id=kyc.id).exists():
                kyc.is_duplicate = True
                kyc.save()
                return True
        if kyc.phone_number:
            if KYC.objects.filter(
                phone_number=kyc.phone_number,
                status='verified'
            ).exclude(id=kyc.id).exists():
                kyc.is_duplicate = True
                kyc.save()
                return True
        return False

    @staticmethod
    def is_user_verified(user) -> bool:
        from .models import KYC
        return KYC.objects.filter(user=user, status='verified').exists()